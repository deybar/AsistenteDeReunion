"""
Asistente de Reunión Local (100% Offline, Confidencial y Privado).
Orquestador Principal, Bandeja del Sistema y Control de Instancia Única.
"""

import os
import sys
import queue
import logging
from typing import Dict, Any

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

LOG_FILE = os.path.join(APP_DIR, "asistente_reunion.log")
log_handlers = [FlushingFileHandler(LOG_FILE, encoding="utf-8", mode="a")]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=log_handlers
)
logger = logging.getLogger("AsistenteReunion.Main")

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from theme_config import load_config, save_config, get_theme_data, THEMES
from audio_mixer_capture import AudioMixerCaptureManager
from audio_recorder import AudioMeetingRecorder
from meeting_transcriber import LiveMeetingTranscriber
from transcript_manager import TranscriptManager
from meeting_agent import MeetingInsightsAgent
from summary_dialog import MeetingSummaryDialog
from meeting_window import MeetingWindow

SOCKET_NAME = "AsistenteReunion_SingleInstance_2026"

def ensure_single_instance(app, on_activate_cb, on_quit_cb=None) -> bool:
    """Evita ejecuciones duplicadas del asistente en segundo plano."""
    test_socket = QLocalSocket()
    test_socket.connectToServer(SOCKET_NAME)
    if test_socket.waitForConnected(800):
        logger.info("Ya existe una instancia del Asistente de Reunión activa. Activando ventana...")
        test_socket.write(b"ACTIVATE")
        test_socket.waitForBytesWritten(400)
        test_socket.disconnectFromServer()
        return False

    QLocalServer.removeServer(SOCKET_NAME)
    server = QLocalServer()
    if server.listen(SOCKET_NAME):
        def handle_connection():
            client = server.nextPendingConnection()
            if client:
                if client.bytesAvailable() > 0 or client.waitForReadyRead(300):
                    data = client.readAll().data().decode("utf-8", errors="ignore")
                    if "QUIT" in data:
                        logger.info("Recibida orden de cierre remoto (QUIT).")
                        if on_quit_cb:
                            on_quit_cb()
                        else:
                            app.quit()
                    elif "ACTIVATE" in data:
                        on_activate_cb()
                client.disconnectFromServer()
        server.newConnection.connect(handle_connection)
        app._instance_server = server
        return True
    return True

def create_tray_icon_pixmap(theme_key: str = "dark_carbon") -> QPixmap:
    """Dibuja un icono vectorial para la bandeja del sistema."""
    t = get_theme_data(theme_key)
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fondo redondeado
    painter.setBrush(QColor(t.get("card_bg", "#121214")))
    painter.setPen(QColor(t.get("border", "#27272a")))
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)

    # Símbolo
    painter.setPen(QColor(t.get("text_accent", "#38bdf8")))
    painter.setFont(QFont("Segoe UI Emoji", 13, QFont.Weight.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "🎙️")
    painter.end()
    return pixmap

class SignalBridge(QObject):
    transcript_received = pyqtSignal(str, str, str, str, float, float)  # timestamp, speaker, text, source_type, t_start, t_end
    audio_level_received = pyqtSignal(float)
    status_received = pyqtSignal(str)

class MeetingAppController:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.config = load_config()

        self.audio_queue = queue.Queue(maxsize=100)
        self.bridge = SignalBridge()

        # 1. Grabador de Audio Maestro en Streaming (.wav)
        self.recorder = AudioMeetingRecorder(sample_rate=16000, channels=1)

        # 2. Gestor de Datos Dual (.md + .json + .wav) y Agente de Inteligencia
        self.transcript_manager = TranscriptManager(base_dir=self.config.get("save_dir", "reuniones"))
        self.meeting_agent = MeetingInsightsAgent(
            ollama_url=self.config.get("ollama_url", "http://localhost:11434"),
            ollama_model=self.config.get("ollama_model", "qwen2.5:3b"),
            ollama_enabled=self.config.get("ollama_enabled", True)
        )

        # 3. Captura de audio multifuente conectado al grabador en streaming
        self.audio_manager = AudioMixerCaptureManager(
            audio_queue=self.audio_queue,
            sample_rate=16000,
            on_level_changed=self.bridge.audio_level_received.emit,
            on_status=self.bridge.status_received.emit,
            recorder=self.recorder
        )

        # 4. Transcriptor Whisper multilingüe con timestamps relativos
        self.transcriber = LiveMeetingTranscriber(
            audio_queue=self.audio_queue,
            model_size=self.config.get("model_size", "base"),
            language=self.config.get("language", "es"),
            sample_rate=16000,
            latency_mode=self.config.get("latency_mode", "ultra_fast"),
            user_label=self.config.get("user_label", "Tú"),
            on_transcript_ready=self.bridge.transcript_received.emit,
            on_status=self.bridge.status_received.emit,
            logger=self.transcript_manager
        )

        # 5. Ventana Flotante (HUD Zen / Modo Cápsula)
        self.window = MeetingWindow(self.config)

        # 6. Conexión de señales
        self._connect_signals()

        # 7. Bandeja del sistema
        self._init_tray_icon()

    def _connect_signals(self):
        self.bridge.transcript_received.connect(self.window.append_transcript_entry)
        self.bridge.audio_level_received.connect(self.window.set_audio_level)

        self.window.toggle_pause_requested.connect(self._on_toggle_pause)
        self.window.audio_mode_changed.connect(self._on_audio_mode_changed)
        self.window.new_session_requested.connect(self._on_new_session)
        self.window.finalize_meeting_requested.connect(self._on_finalize_meeting)
        self.window.open_file_requested.connect(self.transcript_manager.open_current_file)
        self.window.open_audio_requested.connect(self.transcript_manager.open_current_audio)
        self.window.open_folder_requested.connect(self.transcript_manager.open_folder)
        self.window.theme_changed.connect(self._on_theme_changed)
        self.window.latency_mode_changed.connect(self.transcriber.set_latency_mode)
        self.window.model_changed.connect(self._on_model_changed)
        self.window.language_changed.connect(self.transcriber.set_language)

    def _on_model_changed(self, new_model: str):
        logger.info(f"Cambiando modelo Whisper a: {new_model}")
        self.transcriber.change_model_size(new_model)

    def _init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self.window)
        self.tray_icon.setIcon(QIcon(create_tray_icon_pixmap(self.config.get("theme", "dark_carbon"))))
        self.tray_icon.setToolTip("Asistente de Reunión Local (100% Offline)")

        menu = QMenu()
        act_show = menu.addAction("Mostrar Ventana Flotante")
        act_show.triggered.connect(self._activate_window)

        act_minuta = menu.addAction("✨ Generar Minuta y Compromisos")
        act_minuta.triggered.connect(self._on_finalize_meeting)

        menu.addSeparator()

        act_file = menu.addAction("📄 Abrir Archivo .txt Actual")
        act_file.triggered.connect(self.transcript_manager.open_current_file)

        act_folder = menu.addAction("📂 Abrir Carpeta de Reuniones")
        act_folder.triggered.connect(self.transcript_manager.open_folder)

        menu.addSeparator()

        act_quit = menu.addAction("Salir del Asistente")
        act_quit.triggered.connect(self.quit_application)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.window.isVisible():
                self.window.hide()
            else:
                self._activate_window()

    def _activate_window(self):
        self.window.showNormal()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_toggle_pause(self):
        paused = self.window.is_paused
        self.audio_manager.set_paused(paused)

    def _on_audio_mode_changed(self, new_mode: str):
        logger.info(f"Cambiando modo de audio a: {new_mode}")
        self.audio_manager.stop()
        self.audio_manager.start(
            mode=new_mode,
            loopback_device_index=self.config.get("loopback_device_index"),
            mic_device_index=self.config.get("mic_device_index")
        )

    def _on_new_session(self):
        audio_meta = self.recorder.stop_recording()
        if not self.transcript_manager.is_finalized() and len(self.transcript_manager.get_entries()) > 0:
            self.transcript_manager.finalize_meeting(self.meeting_agent, audio_metadata=audio_meta)

        self.transcriber.reset_session()
        self.recorder.start_recording(self.transcript_manager.get_current_wav_path())
        self.window.reset_timer()
        logger.info("Nueva sesión de reunión sincronizada iniciada")

    def _on_finalize_meeting(self):
        """Dispara el análisis del agente, cierra el audio WAV y muestra el diálogo con los compromisos."""
        logger.info("Finalizando reunión, cerrando audio maestro y extrayendo compromisos...")
        audio_meta = self.recorder.stop_recording()
        filepath, report = self.transcript_manager.finalize_meeting(
            self.meeting_agent,
            audio_metadata=audio_meta
        )

        # Mostrar cuadro de diálogo interactivo
        dialog = MeetingSummaryDialog(
            report=report,
            filepath=filepath,
            theme_key=self.config.get("theme", "dark_carbon"),
            parent=self.window
        )
        dialog.exec()

    def _on_theme_changed(self, theme_key: str):
        self.tray_icon.setIcon(QIcon(create_tray_icon_pixmap(theme_key)))

    def start(self):
        self.window.showNormal()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

        # Iniciar carga de modelos en segundo plano
        def on_model_loaded(success: bool, msg: str):
            if success:
                logger.info("Modelo de IA cargado. Iniciando captura y grabación de audio sincronizado...")
                # Iniciar grabación en streaming continuo del archivo WAV maestro
                self.recorder.start_recording(self.transcript_manager.get_current_wav_path())

                # Iniciar captura de audio
                self.audio_manager.start(
                    mode=self.config.get("audio_mode", "mixed"),
                    loopback_device_index=self.config.get("loopback_device_index"),
                    mic_device_index=self.config.get("mic_device_index")
                )
                self.transcriber.start()

        self.transcriber.initialize_model_async(callback=on_model_loaded)

    def quit_application(self):
        logger.info("Cerrando Asistente de Reunión...")
        audio_meta = self.recorder.stop_recording()
        if not self.transcript_manager.is_finalized() and len(self.transcript_manager.get_entries()) > 0:
            try:
                self.transcript_manager.finalize_meeting(self.meeting_agent, audio_metadata=audio_meta)
            except Exception:
                pass

        self.audio_manager.stop()
        self.transcriber.stop()
        self.qapp.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = None
    def activate_cb():
        if controller:
            controller._activate_window()

    def quit_cb():
        if controller:
            controller.quit_application()
        else:
            app.quit()

    if not ensure_single_instance(app, activate_cb, on_quit_cb=quit_cb):
        sys.exit(0)

    controller = MeetingAppController(app)
    controller.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
