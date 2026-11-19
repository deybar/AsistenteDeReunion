"""
Ventana Flotante del Asistente de Reuniones (PyQt6).
Diseño Zen / HUD Cápsula Minimalista con visualizador de audio reactivo en tiempo real.
Permite alternar entre Modo HUD Discreto (cero distracción visual, solo onda y cronómetro)
y Modo Expandido con la transcripción completa en vivo y botón para Generar Minuta.
"""

import sys
import os
import time
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QRect, QRectF, QSize, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QPushButton, QGraphicsDropShadowEffect, QFrame, QSlider,
    QMenu, QSizeGrip, QSizePolicy, QApplication
)
from PyQt6.QtGui import QColor, QFont, QCursor, QAction, QIcon, QTextCursor, QPainter

from theme_config import THEMES, get_theme_data, save_config

class AudioWavePulseWidget(QWidget):
    """Visualizador reactivo de ondas sonoras que pulsa en tiempo real según el volumen de voz."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 22)
        self.level = 0.0  # Rango 0.0 a 1.0
        self.decay_timer = QTimer(self)
        self.decay_timer.timeout.connect(self._decay)
        self.decay_timer.start(45)

    def set_level(self, lvl: float):
        self.level = max(self.level, min(1.0, lvl))
        self.update()

    def _decay(self):
        if self.level > 0.04:
            self.level *= 0.82
            self.update()
        elif self.level != 0.0:
            self.level = 0.0
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 5 barras reactivas armónicas
        num_bars = 5
        bar_w = 4.0
        gap = 4.0
        total_w = num_bars * bar_w + (num_bars - 1) * gap
        start_x = (self.width() - total_w) / 2.0
        mid_y = self.height() / 2.0

        multipliers = [0.45, 0.8, 1.0, 0.8, 0.45]

        for i in range(num_bars):
            h_base = 3.5
            h_dynamic = (self.height() - 6.0) * multipliers[i] * self.level
            bar_h = max(h_base, h_base + h_dynamic)

            x = start_x + i * (bar_w + gap)
            y = mid_y - bar_h / 2.0

            alpha = int(140 + 115 * self.level)
            if self.level > 0.14:
                color = QColor(16, 185, 129, alpha)  # #10b981 verde activo
            else:
                color = QColor(56, 189, 248, alpha)  # #38bdf8 cian escucha

            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 2, 2)
        painter.end()

class DraggableHeader(QFrame):
    """Barra superior que permite arrastrar la ventana flotante."""
    def __init__(self, parent_window):
        super().__init__()
        self.window = parent_window
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.start_drag(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.window.do_drag(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window.end_drag()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class MeetingWindow(QWidget):
    # Señales para comunicación con el controlador principal
    toggle_pause_requested = pyqtSignal()
    audio_mode_changed = pyqtSignal(str)   # "mixed", "loopback", "microphone"
    new_session_requested = pyqtSignal()
    finalize_meeting_requested = pyqtSignal()
    open_file_requested = pyqtSignal()
    open_audio_requested = pyqtSignal()
    open_folder_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)
    latency_mode_changed = pyqtSignal(str)
    model_changed = pyqtSignal(str)
    language_changed = pyqtSignal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.theme_data = get_theme_data(self.config.get("theme", "dark_carbon"))

        self._is_dragging = False
        self._drag_start_offset = QPoint(0, 0)
        self.is_paused = False
        self.audio_mode = self.config.get("audio_mode", "mixed")
        self.font_size = self.config.get("font_size", 14)
        self.show_text_view = self.config.get("show_text_view", False)

        # Cronómetro de reunión en vivo
        self.elapsed_seconds = 0
        self.timer_session = QTimer(self)
        self.timer_session.timeout.connect(self._on_tick_timer)
        self.timer_session.start(1000)

        self._init_ui()
        self.apply_theme(self.config.get("theme", "dark_carbon"))
        self.set_window_opacity_percent(self.config.get("opacity", 94))

        # Posición y tamaño
        x = self.config.get("window_pos_x", 140)
        y = self.config.get("window_pos_y", 680)
        w = max(620, self.config.get("window_width", 720))
        h = self.config.get("window_height", 230) if self.show_text_view else 52
        self.setGeometry(x, y, w, h)

    def _init_ui(self):
        self.setWindowTitle("Asistente de Reunión Local")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Contenedor estilo tarjeta flotante
        self.card = QFrame(self)
        self.card.setObjectName("card")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(10, 6, 10, 6)
        self.card_layout.setSpacing(4)

        # Sombra suave exterior
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 170))
        self.shadow.setOffset(0, 4)
        self.card.setGraphicsEffect(self.shadow)

        # --- HEADER ARRASTRABLE (HUD ZEN CAPSULE) ---
        self.header = DraggableHeader(self)
        self.header.setObjectName("header")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # 1. Tirador
        self.drag_icon = QLabel("⠿", self.header)
        self.drag_icon.setToolTip("Arrastra desde aquí para mover la cápsula por la pantalla")
        self.drag_icon.setStyleSheet("font-size: 13px; font-weight: bold; color: #71717a;")
        header_layout.addWidget(self.drag_icon)

        # 2. Indicador luminoso REC (Grabación + Transcripción en vivo)
        self.status_dot = QLabel("● REC", self.header)
        self.status_dot.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        self.status_dot.setToolTip("Estado: Grabando audio WAV y transcribiendo en vivo")
        header_layout.addWidget(self.status_dot)

        # 3. Cronómetro de la reunión
        self.lbl_timer = QLabel("⏱️ 00:00", self.header)
        self.lbl_timer.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 700; font-family: monospace;")
        self.lbl_timer.setToolTip("Tiempo de reunión grabado en el audio sincronizado")
        header_layout.addWidget(self.lbl_timer)

        # 4. Visualizador Reactivo de Onda de Audio
        self.audio_wave = AudioWavePulseWidget(self.header)
        self.audio_wave.setToolTip("Onda de audio reactiva: se mueve al ritmo de la voz")
        header_layout.addWidget(self.audio_wave)

        # 5. Badge del último interlocutor activo
        self.lbl_speaker_badge = QLabel("🎙️ Escuchando", self.header)
        self.lbl_speaker_badge.setStyleSheet("""
            background-color: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 4px;
        """)
        header_layout.addWidget(self.lbl_speaker_badge)

        header_layout.addStretch()

        # 6. Botón de alternancia de vista de transcripción (HUD Zen vs Texto)
        self.btn_toggle_text = QPushButton("📜 Texto ▴" if self.show_text_view else "📜 Texto ▾", self.header)
        self.btn_toggle_text.setToolTip("Alternar entre Cápsula Zen discreta y Visor de Transcripción completa")
        self.btn_toggle_text.setFixedHeight(22)
        self.btn_toggle_text.setStyleSheet("padding: 2px 7px; font-size: 10px; font-weight: 600;")
        self.btn_toggle_text.clicked.connect(self._toggle_text_view)
        header_layout.addWidget(self.btn_toggle_text)

        # 7. Botón Play / Pausa
        self.btn_pause = QPushButton("⏸", self.header)
        self.btn_pause.setToolTip("Pausar / Reanudar grabación")
        self.btn_pause.setFixedSize(24, 22)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        header_layout.addWidget(self.btn_pause)

        # 8. BOTÓN DESTACADO: GENERAR MINUTA Y COMPROMISOS
        self.btn_minuta = QPushButton("✨ Minuta", self.header)
        self.btn_minuta.setToolTip("Finalizar reunión y generar minuta ejecutiva con compromisos")
        self.btn_minuta.setFixedHeight(22)
        self.btn_minuta.setObjectName("btn_minuta")
        self.btn_minuta.setStyleSheet("""
            background-color: #0284c7;
            color: #ffffff;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            border: none;
        """)
        self.btn_minuta.clicked.connect(self._on_minuta_clicked)
        header_layout.addWidget(self.btn_minuta)

        # 9. Menú Más Opciones (Archivos, Temas, Audio)
        self.btn_more = QPushButton("···", self.header)
        self.btn_more.setToolTip("Más opciones (Archivos .md, audio .wav, modo de audio, temas)")
        self.btn_more.setFixedSize(24, 22)
        self.btn_more.clicked.connect(self._show_more_menu)
        header_layout.addWidget(self.btn_more)

        # 10. Botón Ocultar / Minimizar
        self.btn_close = QPushButton("✕", self.header)
        self.btn_close.setToolTip("Minimizar a la bandeja del sistema")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.clicked.connect(self.hide)
        header_layout.addWidget(self.btn_close)

        self.card_layout.addWidget(self.header)

        # --- ÁREA DE TRANSCRIPCIÓN EN VIVO (Desplegable) ---
        self.transcript_browser = QTextBrowser(self.card)
        self.transcript_browser.setObjectName("transcript_browser")
        self.transcript_browser.setOpenExternalLinks(False)
        self.transcript_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.transcript_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.transcript_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.card_layout.addWidget(self.transcript_browser)

        # Grip de redimensionado inferior
        self.footer = QWidget(self.card)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch()
        self.size_grip = QSizeGrip(self.footer)
        self.size_grip.setFixedSize(14, 14)
        footer_layout.addWidget(self.size_grip)
        self.card_layout.addWidget(self.footer)

        main_layout.addWidget(self.card)

        # Aplicar estado inicial de visibilidad del área de texto
        self._apply_text_view_visibility()

        # Mensaje inicial
        self._append_system_message("🎙️ Asistente de Reunión Local Activo. Grabando audio maestro sincronizado (.wav + .md + .json)...")

    def _apply_text_view_visibility(self):
        """Muestra u oculta el área de texto según el modo seleccionado."""
        if self.show_text_view:
            self.transcript_browser.show()
            self.footer.show()
            self.btn_toggle_text.setText("📜 Texto ▴")
            expanded_h = self.config.get("expanded_height", 230)
            self.setFixedHeight(max(180, expanded_h))
            self.setMaximumHeight(16777215)
        else:
            self.transcript_browser.hide()
            self.footer.hide()
            self.btn_toggle_text.setText("📜 Texto ▾")
            self.setFixedHeight(52)

    def _toggle_text_view(self):
        self.show_text_view = not self.show_text_view
        self.config["show_text_view"] = self.show_text_view
        if self.show_text_view:
            self.config["expanded_height"] = max(200, self.config.get("expanded_height", 230))
        save_config(self.config)
        self._apply_text_view_visibility()

    def _on_tick_timer(self):
        if not self.is_paused:
            self.elapsed_seconds += 1
            m = self.elapsed_seconds // 60
            s = self.elapsed_seconds % 60
            h = m // 60
            m = m % 60
            if h > 0:
                self.lbl_timer.setText(f"⏱️ {h:02d}:{m:02d}:{s:02d}")
            else:
                self.lbl_timer.setText(f"⏱️ {m:02d}:{s:02d}")

    def reset_timer(self):
        self.elapsed_seconds = 0
        self.lbl_timer.setText("⏱️ 00:00")

    def _on_pause_clicked(self):
        self.is_paused = not self.is_paused
        self.btn_pause.setText("▶" if self.is_paused else "⏸")
        if self.is_paused:
            self.status_dot.setText("⏸ PAUSA")
            self.status_dot.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 800;")
        else:
            self.status_dot.setText("● REC")
            self.status_dot.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 800;")
        self.toggle_pause_requested.emit()

    def _on_new_session_clicked(self):
        self.transcript_browser.clear()
        self.reset_timer()
        self._append_system_message("✨ Nueva sesión iniciada. Archivos .wav, .md y .json preparados.")
        self.new_session_requested.emit()

    def _on_minuta_clicked(self):
        self.finalize_meeting_requested.emit()

    def _show_more_menu(self):
        menu = QMenu(self)

        # 1. Nueva Sesión
        act_new = menu.addAction("➕ Iniciar Nueva Sesión Limpia")
        act_new.triggered.connect(self._on_new_session_clicked)

        menu.addSeparator()

        # 2. Archivos sincronizados
        act_open_md = menu.addAction("📄 Abrir Minuta y Transcripción (.md)")
        act_open_md.triggered.connect(self.open_file_requested.emit)

        act_open_wav = menu.addAction("🎵 Reproducir Audio Grabado (.wav)")
        act_open_wav.triggered.connect(self.open_audio_requested.emit)

        act_open_folder = menu.addAction("📂 Abrir Carpeta de Reuniones")
        act_open_folder.triggered.connect(self.open_folder_requested.emit)

        menu.addSeparator()

        # 3. Modo de Audio
        audio_menu = menu.addMenu("🎙️ Fuente de Audio")
        a_mixed = audio_menu.addAction("🎙️+🔊 Dual (PC + Micrófono) [Recomendado]")
        a_mixed.triggered.connect(lambda: self._set_audio_mode("mixed"))
        a_loopback = audio_menu.addAction("🔊 Solo Audio del PC (WASAPI)")
        a_loopback.triggered.connect(lambda: self._set_audio_mode("loopback"))
        a_mic = audio_menu.addAction("🎙️ Solo Micrófono Físico")
        a_mic.triggered.connect(lambda: self._set_audio_mode("microphone"))

        # 4. Latencia
        lat_menu = menu.addMenu("⚡ Latencia de Transcripción")
        act_uf = lat_menu.addAction("⚡ Ultra-Rápido (~1s)")
        act_uf.triggered.connect(lambda: self._set_latency("ultra_fast"))
        act_bal = lat_menu.addAction("⚖️ Equilibrado (~2s)")
        act_bal.triggered.connect(lambda: self._set_latency("balanced"))
        act_ext = lat_menu.addAction("📖 Frases Largas (~3.5s)")
        act_ext.triggered.connect(lambda: self._set_latency("extended"))

        # 5. Idioma
        lang_menu = menu.addMenu("🌐 Idioma de Voz")
        act_es = lang_menu.addAction("🇪🇸 Español (Optimizado)")
        act_es.triggered.connect(lambda: self._set_language("es"))
        act_auto = lang_menu.addAction("🌐 Detección Automática (ES/EN)")
        act_auto.triggered.connect(lambda: self._set_language("auto"))
        act_en = lang_menu.addAction("🇺🇸 Inglés")
        act_en.triggered.connect(lambda: self._set_language("en"))

        menu.addSeparator()

        # 6. Temas
        theme_menu = menu.addMenu("🎨 Cambiar Tema Visual")
        for k, v in THEMES.items():
            act = theme_menu.addAction(v["name"])
            act.triggered.connect(lambda checked, key=k: self._set_theme(key))

        # 7. Opacidad
        opac_menu = menu.addMenu("👁️ Opacidad de Ventana")
        for op in [100, 94, 88, 75]:
            act_op = opac_menu.addAction(f"{op}%")
            act_op.triggered.connect(lambda checked, val=op: self.set_window_opacity_percent(val))

        menu.exec(QCursor.pos())

    def _set_audio_mode(self, mode: str):
        self.audio_mode = mode
        self.config["audio_mode"] = mode
        save_config(self.config)
        self.audio_mode_changed.emit(mode)

    def _set_latency(self, mode: str):
        self.config["latency_mode"] = mode
        save_config(self.config)
        self.latency_mode_changed.emit(mode)

    def _set_language(self, lang_code: str):
        self.config["language"] = lang_code
        save_config(self.config)
        self.language_changed.emit(lang_code)

    def _set_theme(self, theme_key: str):
        self.config["theme"] = theme_key
        save_config(self.config)
        self.apply_theme(theme_key)
        self.theme_changed.emit(theme_key)

    def set_window_opacity_percent(self, percent: int):
        clamped = max(50, min(100, percent))
        self.setWindowOpacity(clamped / 100.0)
        self.config["opacity"] = clamped
        save_config(self.config)

    def apply_theme(self, theme_key: str):
        self.theme_data = get_theme_data(theme_key)
        t = self.theme_data
        rgb = t.get("card_bg_rgb", "18, 18, 20")
        card_bg = f"rgba({rgb}, 0.94)"

        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {card_bg};
                border: 1px solid {t.get('border', '#27272a')};
                border-radius: 10px;
            }}
            QTextBrowser#transcript_browser {{
                background-color: transparent;
                border: none;
                color: {t.get('text_main', '#f4f4f5')};
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: {self.font_size}px;
                line-height: 1.45;
            }}
            QPushButton {{
                background-color: {t.get('btn_bg', '#18181b')};
                color: {t.get('text_main', '#f4f4f5')};
                border: 1px solid {t.get('btn_border', '#3f3f46')};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {t.get('btn_bg_hover', '#27272a')};
            }}
            QMenu {{
                background-color: {t.get('card_bg', '#121214')};
                color: {t.get('text_main', '#f4f4f5')};
                border: 1px solid {t.get('border', '#27272a')};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {t.get('btn_bg_hover', '#27272a')};
            }}
        """)

    def _append_system_message(self, msg: str):
        t = self.theme_data
        muted = t.get("text_muted", "#a1a1aa")
        html = f"<div style='color: {muted}; font-size: 11px; margin-bottom: 6px;'><i>{msg}</i></div>"
        self.transcript_browser.append(html)
        self.transcript_browser.moveCursor(QTextCursor.MoveOperation.End)

    def append_transcript_entry(
        self,
        timestamp_str: str,
        speaker: str,
        text: str,
        source_type: str = "pc",
        start_sec: float = 0.0,
        end_sec: float = 0.0
    ):
        """Muestra una intervención en vivo con color de hablante y marca de tiempo."""
        t = self.theme_data
        is_self = ("Tú" in speaker or source_type == "mic")
        speaker_color = t.get("speaker_self", "#10b981") if is_self else t.get("speaker_other", "#60a5fa")
        text_color = t.get("text_main", "#f4f4f5")
        muted_color = t.get("text_muted", "#a1a1aa")

        # Actualizar el badge en la cápsula HUD Zen
        icon = "🎙️" if is_self else "🔊"
        self.lbl_speaker_badge.setText(f"{icon} {speaker}")
        self.lbl_speaker_badge.setToolTip(f"Última frase: \"{text}\"")

        # Rango de tiempo relativo si está disponible
        time_display = timestamp_str
        if end_sec > 0:
            s_fmt = f"{int(start_sec)//60:02d}:{int(start_sec)%60:02d}"
            e_fmt = f"{int(end_sec)//60:02d}:{int(end_sec)%60:02d}"
            time_display = f"[{s_fmt} ➔ {e_fmt}] ({timestamp_str})"

        html = (
            f"<div style='margin-bottom: 8px; line-height: 1.4;'>"
            f"  <span style='color: {muted_color}; font-size: {max(9, self.font_size - 4)}px;'>{time_display}</span> "
            f"  <b style='color: {speaker_color}; font-size: {max(11, self.font_size - 1)}px;'>[{speaker}]</b>: "
            f"  <span style='color: {text_color}; font-size: {self.font_size}px;'>{text}</span>"
            f"</div>"
        )
        self.transcript_browser.append(html)
        self.transcript_browser.moveCursor(QTextCursor.MoveOperation.End)

    def set_audio_level(self, level: float):
        """Alimenta la onda de audio reactiva en la cápsula Zen."""
        if not self.is_paused:
            self.audio_wave.set_level(level)

    # Gestión de arrastre de la cápsula
    def start_drag(self, global_pos: QPoint):
        self._is_dragging = True
        self._drag_start_offset = global_pos - self.pos()

    def do_drag(self, global_pos: QPoint):
        if self._is_dragging:
            self.move(global_pos - self._drag_start_offset)

    def end_drag(self):
        self._is_dragging = False
        self.config["window_pos_x"] = self.pos().x()
        self.config["window_pos_y"] = self.pos().y()
        self.config["window_width"] = self.width()
        if self.show_text_view:
            self.config["expanded_height"] = self.height()
        save_config(self.config)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.config["window_width"] = self.width()
        if self.show_text_view:
            self.config["expanded_height"] = self.height()
