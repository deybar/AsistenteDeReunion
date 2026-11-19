"""
Motor de Transcripción Multilingüe de Reuniones en Vivo (100% Local).
Optimizado para ultra-baja latencia en CPU (< 1s por frase).
Soporta Español e Inglés con greedy decoding y sin sobrecarga de detección redundante.
"""

import threading
import queue
import time
import os
from datetime import datetime
from typing import Optional, Callable, Dict, Any, Tuple
import numpy as np
from faster_whisper import WhisperModel

from speaker_diarizer import MeetingSpeakerDiarizer
from transcript_manager import TranscriptManager

# Presets de latencia optimizados para tiempo real fluido en CPU
LATENCY_PRESETS: Dict[str, Dict[str, Any]] = {
    "ultra_fast": {
        "name": "⚡ Ultra-Rápido (~1s)",
        "min_speech": 0.28,      # 280 ms mínimo de voz
        "max_speech": 2.2,       # Corta y transcribe a los 2.2s de discurso continuo
        "pause_trigger": 0.25,   # 250 ms de pausa natural disparan transcripción inmediata
        "silence_rms": 0.007     # Umbral de silencio
    },
    "balanced": {
        "name": "⚖️ Equilibrado (~2s)",
        "min_speech": 0.38,
        "max_speech": 3.2,
        "pause_trigger": 0.35,
        "silence_rms": 0.008
    },
    "extended": {
        "name": "📖 Frases Largas (~3.5s)",
        "min_speech": 0.50,
        "max_speech": 4.5,
        "pause_trigger": 0.45,
        "silence_rms": 0.009
    }
}

class LiveMeetingTranscriber:
    def __init__(
        self,
        audio_queue: queue.Queue,
        model_size: str = "tiny",
        language: str = "es",
        sample_rate: int = 16000,
        latency_mode: str = "ultra_fast",
        user_label: str = "Tú",
        on_transcript_ready: Optional[Callable[[str, str, str, str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        logger: Optional[TranscriptManager] = None
    ):
        self.audio_queue = audio_queue
        self.model_size = model_size
        self.language = language
        self.sample_rate = sample_rate
        self.latency_mode = latency_mode if latency_mode in LATENCY_PRESETS else "ultra_fast"
        self.user_label = user_label
        self.on_transcript_ready = on_transcript_ready
        self.on_status = on_status
        self.logger = logger

        self.whisper_model: Optional[WhisperModel] = None
        self.diarizer = MeetingSpeakerDiarizer(user_label=self.user_label)

        # Cola desacoplada de tamaño pequeño para garantizar que SIEMPRE se procesa lo actual
        self._transcribe_queue: queue.Queue = queue.Queue(maxsize=3)

        self.is_running = False
        self.is_model_loaded = False
        self._audio_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def update_status(self, msg: str):
        if self.on_status:
            self.on_status(msg)

    def set_latency_mode(self, mode_key: str):
        if mode_key in LATENCY_PRESETS:
            self.latency_mode = mode_key
            self.update_status(f"Modo de latencia: {LATENCY_PRESETS[mode_key]['name']}")

    def set_language(self, new_lang: str):
        self.language = new_lang
        label = {"es": "Español (Ultra-rápido)", "auto": "Detección Automática", "en": "Inglés"}.get(new_lang, new_lang)
        self.update_status(f"Idioma: {label}")

    def change_model_size(self, new_model_size: str, on_done: Optional[Callable] = None):
        if new_model_size != self.model_size:
            self.model_size = new_model_size
            self.is_model_loaded = False
            self.initialize_model_async(callback=on_done)

    def set_user_label(self, label: str):
        self.user_label = label
        self.diarizer.set_user_label(label)

    def initialize_model_async(self, callback: Optional[Callable[[bool, str], None]] = None):
        """Carga el modelo Whisper multilingüe optimizado para CPU."""
        def _load():
            try:
                self.update_status(f"Cargando modelo Whisper '{self.model_size}' optimizado para CPU...")
                # Asignar 3 hilos en CPU de 4 núcleos para no saturar el sistema
                cores = os.cpu_count() or 4
                threads = max(2, min(4, cores - 1)) if cores > 2 else cores

                self.whisper_model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=threads,
                    num_workers=1
                )
                self.is_model_loaded = True
                lang_str = "Español" if self.language == "es" else ("Auto" if self.language == "auto" else "Inglés")
                self.update_status(f"Asistente listo [{self.model_size} | {lang_str}] (100% Offline)")
                if callback:
                    callback(True, "Modelo cargado con éxito")
            except Exception as e:
                self.update_status(f"Error al cargar modelo Whisper: {e}")
                if callback:
                    callback(False, str(e))

        thread = threading.Thread(target=_load, daemon=True)
        thread.start()

    def start(self):
        """Inicia los hilos de segmentación de audio e inferencia."""
        with self._lock:
            if self.is_running:
                return
            self.is_running = True

            # 1. Hilo de segmentación VAD ultra-rápido
            self._audio_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self._audio_thread.start()

            # 2. Hilo consumidor de inferencia Whisper
            self._worker_thread = threading.Thread(target=self._transcription_worker_loop, daemon=True)
            self._worker_thread.start()

    def stop(self):
        with self._lock:
            self.is_running = False

    def reset_session(self):
        """Reinicia el diarizador y abre una nueva sesión de archivo."""
        self.diarizer.reset()
        if self.logger:
            return self.logger.new_session()
        return None

    def _process_audio_loop(self):
        """
        Segmentador continuo de audio:
        Agrupa paquetes de 100 ms y detecta pausas naturales de voz (< 250ms)
        para disparar la transcripción al instante sin acumular retardo.
        Calcula los desplazamientos de tiempo relativos (t_start y t_end) respecto al audio.
        """
        buffer_chunks = []
        silence_duration = 0.0
        speech_duration = 0.0
        last_source = "pc"
        total_audio_sec = 0.0
        speech_start_sec = 0.0

        while self.is_running:
            preset = LATENCY_PRESETS.get(self.latency_mode, LATENCY_PRESETS["ultra_fast"])
            silence_threshold = preset["silence_rms"]
            min_speech = preset["min_speech"]
            max_speech = preset["max_speech"]
            pause_trigger = preset["pause_trigger"]

            try:
                item = self.audio_queue.get(timeout=0.06)
            except queue.Empty:
                continue

            if isinstance(item, tuple):
                chunk, source_type = item
            else:
                chunk, source_type = item, "pc"

            chunk_duration = len(chunk) / self.sample_rate
            total_audio_sec += chunk_duration

            rms = float(np.sqrt(np.mean(chunk ** 2)))
            is_speech = (rms >= silence_threshold)

            # Cambio de interlocutor entre PC y Micrófono
            if buffer_chunks and source_type != last_source and speech_duration >= min_speech:
                full_audio = np.concatenate(buffer_chunks)
                t_start = speech_start_sec
                t_end = total_audio_sec
                if self._transcribe_queue.full():
                    try:
                        self._transcribe_queue.get_nowait()
                    except queue.Empty:
                        pass
                self._transcribe_queue.put((full_audio, last_source, silence_duration, t_start, t_end))
                buffer_chunks = []
                speech_duration = 0.0
                silence_duration = 0.0

            last_source = source_type

            if is_speech:
                if not buffer_chunks:
                    speech_start_sec = max(0.0, total_audio_sec - chunk_duration)
                buffer_chunks.append(chunk)
                speech_duration += chunk_duration
                silence_duration = 0.0
            else:
                if buffer_chunks:
                    buffer_chunks.append(chunk)
                    silence_duration += chunk_duration

            should_transcribe = False
            if speech_duration >= min_speech:
                if silence_duration >= pause_trigger:
                    should_transcribe = True
                elif speech_duration >= max_speech:
                    should_transcribe = True

            if should_transcribe:
                full_audio = np.concatenate(buffer_chunks)
                pause_time = silence_duration
                t_start = speech_start_sec
                t_end = total_audio_sec

                buffer_chunks = []
                speech_duration = 0.0
                silence_duration = 0.0

                # Descarte de bloques antiguos si hay sobrecarga (mantiene siempre el tiempo real estricto)
                if self._transcribe_queue.full():
                    try:
                        self._transcribe_queue.get_nowait()
                    except queue.Empty:
                        pass

                self._transcribe_queue.put((full_audio, source_type, pause_time, t_start, t_end))

            elif not is_speech and not buffer_chunks:
                silence_duration += chunk_duration

    def _transcription_worker_loop(self):
        """Hilo de inferencia Whisper que consume los fragmentos de audio preparados."""
        while self.is_running:
            try:
                item = self._transcribe_queue.get(timeout=0.08)
            except queue.Empty:
                continue

            if not self.whisper_model or not self.is_model_loaded:
                continue

            if len(item) == 5:
                audio, source_type, pause_time, t_start, t_end = item
            else:
                audio, source_type, pause_time = item[:3]
                t_start, t_end = 0.0, 0.0

            self._transcribe_chunk(audio, source_type, pause_time, t_start, t_end)

    def _transcribe_chunk(
        self,
        audio: np.ndarray,
        source_type: str,
        pause_duration: float,
        t_start: float = 0.0,
        t_end: float = 0.0
    ):
        try:
            # 1. Identificar interlocutor (< 3 ms)
            speaker = self.diarizer.identify_speaker(
                audio,
                source_type=source_type,
                sample_rate=self.sample_rate,
                pause_duration=pause_duration
            )

            # 2. Transcripción con Faster-Whisper
            audio_duration = len(audio) / self.sample_rate
            use_vad = (audio_duration >= 3.2)

            # Si el idioma fijado es "es", se omite la detección de 99 idiomas (4x más rápido)
            target_lang = None if self.language == "auto" else self.language

            segments, info = self.whisper_model.transcribe(
                audio,
                beam_size=1,
                best_of=1,
                language=target_lang,
                condition_on_previous_text=False,
                without_timestamps=True,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                no_speech_threshold=0.6,
                vad_filter=use_vad,
                vad_parameters=dict(min_silence_duration_ms=250) if use_vad else None
            )

            text_list = []
            for seg in segments:
                t = seg.text.strip()
                if t:
                    text_list.append(t)

            if not text_list:
                return

            full_text = " ".join(text_list).strip()

            # Filtro básico de alucinaciones en silencios
            alucinations = [".", "..", "...", "you", "thank you.", "bye.", "gracias", "subtítulos", "subtitulado"]
            if not full_text or full_text.lower() in alucinations:
                if len(audio) < self.sample_rate * 0.6:
                    return

            timestamp_str = datetime.now().strftime("%H:%M:%S")

            # 3. Registrar en archivo dual .md + .json + .txt con offsets relativos
            if self.logger:
                self.logger.log_entry(
                    timestamp_str=timestamp_str,
                    speaker=speaker,
                    text=full_text,
                    start_sec=t_start,
                    end_sec=t_end,
                    source_type=source_type
                )

            # 4. Notificar a la interfaz de usuario
            if self.on_transcript_ready:
                try:
                    self.on_transcript_ready(timestamp_str, speaker, full_text, source_type, t_start, t_end)
                except TypeError:
                    self.on_transcript_ready(timestamp_str, speaker, full_text, source_type)

        except Exception:
            pass
