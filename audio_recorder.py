"""
Grabador de Audio en Streaming para Reuniones (100% Local / WAV PCM).
Escribe en tiempo real el audio mixto (Micrófono + WASAPI Loopback) directamente
a un archivo .wav estándar de 16 kHz mono.
Diseñado para cero impacto en memoria RAM y sincronización milimétrica con el texto transcrito.
"""

import os
import wave
import threading
import time
from typing import Optional, Dict, Any
import numpy as np

class AudioMeetingRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.current_filepath: Optional[str] = None
        self._wave_file: Optional[wave.Wave_write] = None
        self._lock = threading.Lock()

        self.is_recording = False
        self.is_paused = False
        self.total_samples_written = 0
        self.start_timestamp: float = 0.0

    def start_recording(self, filepath: str) -> bool:
        """Inicia un nuevo archivo .wav y prepara el streaming a disco."""
        with self._lock:
            if self.is_recording:
                self.stop_recording()

            # Asegurar que el directorio contenedor exista
            folder = os.path.dirname(os.path.abspath(filepath))
            os.makedirs(folder, exist_ok=True)

            try:
                self._wave_file = wave.open(filepath, "wb")
                self._wave_file.setnchannels(self.channels)
                self._wave_file.setsampwidth(2)  # 16-bit PCM (2 bytes por muestra)
                self._wave_file.setframerate(self.sample_rate)

                self.current_filepath = filepath
                self.is_recording = True
                self.is_paused = False
                self.total_samples_written = 0
                self.start_timestamp = time.time()
                return True
            except Exception as e:
                print(f"[ERROR AudioRecorder] No se pudo crear archivo WAV '{filepath}': {e}")
                self._wave_file = None
                self.is_recording = False
                return False

    def write_chunk(self, audio_data: np.ndarray):
        """
        Escribe un bloque de audio float32 (rango [-1.0, 1.0]) a disco en formato PCM 16-bit.
        Se ejecuta de forma ultra-rápida y continua sin almacenar en memoria RAM.
        """
        if not self.is_recording or self.is_paused or self._wave_file is None:
            return

        with self._lock:
            try:
                # Convertir de float32 [-1.0, 1.0] a int16 [-32768, 32767]
                clamped = np.clip(audio_data, -1.0, 1.0)
                int16_samples = (clamped * 32767.0).astype(np.int16)

                raw_bytes = int16_samples.tobytes()
                self._wave_file.writeframes(raw_bytes)
                self.total_samples_written += len(int16_samples)
            except Exception as e:
                print(f"[ERROR AudioRecorder] Error al escribir bloque de audio: {e}")

    def set_paused(self, paused: bool):
        with self._lock:
            self.is_paused = paused

    def get_current_audio_time_sec(self) -> float:
        """Retorna el tiempo de audio exacto grabado hasta el momento en segundos."""
        return self.total_samples_written / float(self.sample_rate)

    def stop_recording(self) -> Optional[Dict[str, Any]]:
        """Finaliza el archivo WAV, asegura los encabezados en disco y retorna metadatos."""
        with self._lock:
            if not self.is_recording or self._wave_file is None:
                return None

            filepath = self.current_filepath
            duration_sec = self.get_current_audio_time_sec()

            try:
                self._wave_file.close()
            except Exception as e:
                print(f"[ERROR AudioRecorder] Error al cerrar archivo WAV: {e}")

            self._wave_file = None
            self.is_recording = False
            self.is_paused = False

            # Calcular tamaño de archivo en MB
            file_size_mb = 0.0
            if filepath and os.path.exists(filepath):
                try:
                    file_size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
                except Exception:
                    pass

            return {
                "filepath": filepath,
                "filename": os.path.basename(filepath) if filepath else "",
                "duration_seconds": round(duration_sec, 2),
                "duration_formatted": self.format_seconds(duration_sec),
                "sample_rate": self.sample_rate,
                "file_size_mb": file_size_mb
            }

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Formatea segundos en HH:MM:SS."""
        secs = int(seconds)
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
