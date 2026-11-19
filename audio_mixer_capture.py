"""
Capturador de Audio Multifuente en Tiempo Real (WASAPI Loopback + Micrófono Dual).
Permite capturar simultáneamente:
1. Audio interno del PC (Teams, Zoom, Google Meet, navegadores) -> Colegas
2. Micrófono físico local -> Tu propia voz
Remuestrea en vivo a 16kHz mono y etiqueta el origen para una diarización perfecta.
"""

import threading
import queue
import time
from typing import Optional, Callable, List, Dict, Tuple, Any
import numpy as np
import pyaudiowpatch as pyaudio
from scipy import signal

class AudioMixerCaptureManager:
    def __init__(
        self,
        audio_queue: queue.Queue,
        sample_rate: int = 16000,
        on_level_changed: Optional[Callable[[float], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        recorder: Optional[Any] = None
    ):
        self.audio_queue = audio_queue
        self.target_rate = sample_rate
        self.on_level_changed = on_level_changed
        self.on_status = on_status
        self.recorder = recorder

        self.p: Optional[pyaudio.PyAudio] = None
        self.loopback_stream = None
        self.mic_stream = None
        self.silent_stream = None  # Mantiene activo el reloj WASAPI

        self.is_running = False
        self.is_paused = False

        self.current_mode = "mixed"  # "mixed", "loopback", "microphone"
        self.loopback_device_index: Optional[int] = None
        self.mic_device_index: Optional[int] = None

        self.loopback_native_rate = 48000
        self.loopback_channels = 2
        self.mic_native_rate = 48000
        self.mic_channels = 1

        self._lock = threading.Lock()
        self._last_rms_pc = 0.0
        self._last_rms_mic = 0.0

    def update_status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def get_available_devices(self) -> Dict[str, List[Dict]]:
        """Lista los dispositivos loopback y micrófonos disponibles en Windows."""
        p = pyaudio.PyAudio()
        devices = {"loopback": [], "microphone": []}
        try:
            # Dispositivos de salida con soporte Loopback (WASAPI)
            for dev in p.get_loopback_device_info_generator():
                devices["loopback"].append({
                    "index": dev["index"],
                    "name": dev["name"],
                    "rate": int(dev["defaultSampleRate"]),
                    "channels": dev["maxInputChannels"]
                })
            # Micrófonos y entradas de grabación físicas
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev["maxInputChannels"] > 0 and not dev.get("isLoopbackDevice", False):
                    devices["microphone"].append({
                        "index": dev["index"],
                        "name": dev["name"],
                        "rate": int(dev["defaultSampleRate"]),
                        "channels": dev["maxInputChannels"]
                    })
        finally:
            p.terminate()
        return devices

    def _find_default_loopback_device(self, p: pyaudio.PyAudio) -> Optional[Dict]:
        """Busca el dispositivo loopback asociado a los altavoces predeterminados de Windows."""
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            for dev in p.get_loopback_device_info_generator():
                if default_speakers["name"] in dev["name"]:
                    return dev

            for dev in p.get_loopback_device_info_generator():
                return dev
        except Exception as e:
            self.update_status(f"Aviso loopback WASAPI: {e}")
        return None

    def start(
        self,
        mode: str = "mixed",
        loopback_device_index: Optional[int] = None,
        mic_device_index: Optional[int] = None
    ):
        """Inicia la captura multicanal en un hilo de fondo."""
        with self._lock:
            if self.is_running:
                self.stop()

            self.current_mode = mode
            self.loopback_device_index = loopback_device_index
            self.mic_device_index = mic_device_index
            self.is_running = True
            self.is_paused = False

            thread = threading.Thread(target=self._run_capture, daemon=True)
            thread.start()

    def stop(self):
        """Detiene todos los streams de audio y libera los recursos."""
        with self._lock:
            self.is_running = False

        for stream in [self.loopback_stream, self.mic_stream, self.silent_stream]:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
        self.loopback_stream = None
        self.mic_stream = None
        self.silent_stream = None

        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None

    def set_paused(self, paused: bool):
        self.is_paused = paused
        if self.recorder:
            self.recorder.set_paused(paused)

    def set_recorder(self, recorder: Any):
        with self._lock:
            self.recorder = recorder

    def _resample_audio(self, audio_data: np.ndarray, native_rate: int) -> np.ndarray:
        """Remuestrea un arreglo de audio a 16000 Hz mono con scipy.signal.resample_poly."""
        if native_rate == self.target_rate:
            return audio_data
        gcd = np.gcd(native_rate, self.target_rate)
        up = self.target_rate // gcd
        down = native_rate // gcd
        return signal.resample_poly(audio_data, up, down).astype(np.float32)

    def _loopback_callback(self, in_data, frame_count, time_info, status):
        """Callback invocado por el stream de sonido del PC (WASAPI Loopback)."""
        if not self.is_running or self.is_paused or not in_data:
            return (None, pyaudio.paContinue)

        try:
            audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
            if self.loopback_channels > 1:
                audio_data = audio_data.reshape(-1, self.loopback_channels)
                audio_data = np.mean(audio_data, axis=1)

            rms = float(np.sqrt(np.mean(audio_data ** 2)))
            self._last_rms_pc = rms
            self._emit_combined_level()

            resampled = self._resample_audio(audio_data, self.loopback_native_rate)

            # Escribir en streaming continuo en el archivo WAV de la sesión
            if self.recorder and not self.is_paused:
                self.recorder.write_chunk(resampled)

            # Encolar como fuente "pc"
            self.audio_queue.put((resampled, "pc"))
        except Exception:
            pass

        return (None, pyaudio.paContinue)

    def _mic_callback(self, in_data, frame_count, time_info, status):
        """Callback invocado por el micrófono físico."""
        if not self.is_running or self.is_paused or not in_data:
            return (None, pyaudio.paContinue)

        try:
            audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
            if self.mic_channels > 1:
                audio_data = audio_data.reshape(-1, self.mic_channels)
                audio_data = np.mean(audio_data, axis=1)

            rms = float(np.sqrt(np.mean(audio_data ** 2)))
            self._last_rms_mic = rms
            self._emit_combined_level()

            resampled = self._resample_audio(audio_data, self.mic_native_rate)

            # Escribir en streaming continuo en el archivo WAV de la sesión
            if self.recorder and not self.is_paused:
                self.recorder.write_chunk(resampled)

            # Encolar como fuente "mic"
            self.audio_queue.put((resampled, "mic"))
        except Exception:
            pass

        return (None, pyaudio.paContinue)

    def _emit_combined_level(self):
        if self.on_level_changed:
            max_rms = max(self._last_rms_pc, self._last_rms_mic)
            self.on_level_changed(min(1.0, max_rms * 5.0))

    def _run_capture(self):
        try:
            self.p = pyaudio.PyAudio()

            # 1. Configurar Audio del PC (Loopback) si aplica
            if self.current_mode in ["mixed", "loopback"]:
                target_lb = None
                if self.loopback_device_index is not None:
                    target_lb = self.p.get_device_info_by_index(self.loopback_device_index)
                else:
                    target_lb = self._find_default_loopback_device(self.p)

                if target_lb:
                    self.loopback_native_rate = int(target_lb["defaultSampleRate"])
                    self.loopback_channels = max(1, target_lb["maxInputChannels"])
                    frames_per_buf_lb = int(self.loopback_native_rate * 0.1)

                    # Iniciar stream silencioso para mantener activo el reloj de audio
                    try:
                        wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                        self.silent_stream = self.p.open(
                            format=pyaudio.paInt16,
                            channels=2,
                            rate=self.loopback_native_rate,
                            output=True,
                            output_device_index=wasapi_info["defaultOutputDevice"],
                            frames_per_buffer=1024
                        )
                    except Exception:
                        pass

                    self.loopback_stream = self.p.open(
                        format=pyaudio.paInt16,
                        channels=self.loopback_channels,
                        rate=self.loopback_native_rate,
                        input=True,
                        input_device_index=target_lb["index"],
                        frames_per_buffer=frames_per_buf_lb,
                        stream_callback=self._loopback_callback
                    )
                    self.loopback_stream.start_stream()
                else:
                    self.update_status("Aviso: No se encontró dispositivo de altavoces loopback.")

            # 2. Configurar Micrófono Físico si aplica
            if self.current_mode in ["mixed", "microphone"]:
                target_mic = None
                try:
                    if self.mic_device_index is not None:
                        target_mic = self.p.get_device_info_by_index(self.mic_device_index)
                    else:
                        target_mic = self.p.get_default_input_device_info()
                except Exception:
                    pass

                if target_mic:
                    self.mic_native_rate = int(target_mic["defaultSampleRate"])
                    self.mic_channels = max(1, target_mic["maxInputChannels"])
                    frames_per_buf_mic = int(self.mic_native_rate * 0.1)

                    self.mic_stream = self.p.open(
                        format=pyaudio.paInt16,
                        channels=self.mic_channels,
                        rate=self.mic_native_rate,
                        input=True,
                        input_device_index=target_mic["index"],
                        frames_per_buffer=frames_per_buf_mic,
                        stream_callback=self._mic_callback
                    )
                    self.mic_stream.start_stream()
                else:
                    self.update_status("Aviso: No se encontró micrófono disponible.")

            status_text = {
                "mixed": "🎙️+🔊 Capturando Reunión Completa (PC + Micrófono)",
                "loopback": "🔊 Capturando Solo Audio del PC",
                "microphone": "🎙️ Capturando Solo Micrófono"
            }.get(self.current_mode, "Captura activa")
            self.update_status(status_text)

            # Bucle de mantenimiento del reloj de audio WASAPI
            while self.is_running:
                if self.silent_stream and not self.is_paused:
                    try:
                        self.silent_stream.write(b"\x00" * 1024 * 4, exception_on_underflow=False)
                    except Exception:
                        pass
                time.sleep(0.05)

        except Exception as e:
            self.update_status(f"Error en captura de audio: {e}")
        finally:
            self.stop()
