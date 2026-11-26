"""
Motor de Transcripción Multilingüe de Reuniones en Vivo (100% Local).
Usa Silero VAD v6 (ONNX) neuronal para detección de habla real resistente a ruido/música,
acondicionamiento acústico (filtro pasa-altos 80Hz + control automático de ganancia AGC),
Faster-Whisper con contexto continuo y bloqueo estricto de bucles de alucinación.
"""

import re
import threading
import queue
import os
from collections import deque
from datetime import datetime
from typing import Optional, Callable, Dict, Any
import numpy as np
from scipy import signal as scipy_signal
from faster_whisper import WhisperModel
from faster_whisper.vad import get_vad_model

from speaker_diarizer import MeetingSpeakerDiarizer
from transcript_manager import TranscriptManager

# Presets de latencia con ventanas naturales para evitar cortes a mitad de palabra
LATENCY_PRESETS: Dict[str, Dict[str, Any]] = {
    "ultra_fast": {
        "name": "⚡ Ultra-Rápido (~1.5s)",
        "min_speech": 0.55,      # 550 ms mínimo de habla neuronal
        "max_speech": 5.4,       # Ventana máxima antes de buscar valle entre palabras
        "pause_trigger": 0.35,   # 350 ms de pausa natural disparan transcripción
        "silence_rms": 0.008     # Umbral fallback solo para tests sintéticos sin modelo
    },
    "balanced": {
        "name": "⚖️ Equilibrado (~2.5s)",
        "min_speech": 0.75,
        "max_speech": 7.2,
        "pause_trigger": 0.45,
        "silence_rms": 0.008
    },
    "extended": {
        "name": "📖 Frases Largas (~4s)",
        "min_speech": 1.00,
        "max_speech": 10.0,
        "pause_trigger": 0.60,
        "silence_rms": 0.009
    }
}

_TECH_PROMPT_ES = (
    "Hola, en esta sesión hablaremos de Espressif, el dispositivo ESP-Mosaico, "
    "placas ESP8266 y ESP32, Arduino, microcontroladores e inteligencia artificial."
)

_TECH_PROMPT_EN = (
    "Hello, in this technical session we discuss Raspberry Pi, Arduino, ESP32 "
    "microcontrollers, hardware architecture, IoT prototyping, and software engineering."
)

_TECH_CORRECTIONS_ES = [
    (
        re.compile(r"\bmicro\s+controlador(?:es)?\b", re.IGNORECASE),
        lambda m: "microcontroladores" if m.group(0).lower().endswith("es") else "microcontrolador"
    ),
    (
        re.compile(r"\b(?:conmigo|mímico|micoc?)\s+controlador(?:es)?\b", re.IGNORECASE),
        lambda m: "microcontroladores" if m.group(0).lower().endswith("es") else "microcontrolador"
    ),
    (
        re.compile(r"\bmicocontrolador(?:es)?\b", re.IGNORECASE),
        lambda m: "microcontroladores" if m.group(0).lower().endswith("es") else "microcontrolador"
    ),
    (re.compile(r"\b(?:que\s+se\s+pemos\s+aco|espmosico|esp\s+mosaico)\b", re.IGNORECASE), "ESP-Mosaico"),
    (re.compile(r"\b(?:psp|sp|esp)\s*-?\s*8266\b", re.IGNORECASE), "ESP8266"),
    (re.compile(r"\besp\s*-?\s*p?32\b", re.IGNORECASE), "ESP32"),
    (re.compile(r"\bexpressif\b", re.IGNORECASE), "Espressif"),
    (re.compile(r"\bespressif\b", re.IGNORECASE), "Espressif"),
    (re.compile(r"\bplaca\s+(?:a\s+2\s+áreas|segunda\s+área)\b", re.IGNORECASE), "placa secundaria"),
    (re.compile(r"\b(?:suelcosis\s*tema|suelco\s+sistema)\b", re.IGNORECASE), "su ecosistema"),
    (re.compile(r"\bcon\s+vetrólica\b", re.IGNORECASE), "con electrónica"),
    (re.compile(r"\bdispuesto\s+positivo\b", re.IGNORECASE), "dispositivo"),
]


def _refine_technical_text(text: str, language: str = "es") -> str:
    """Corrige confusiones fonéticas frecuentes de vocabulario técnico tras la inferencia ASR."""
    if not text or language == "en":
        return text
    refined = text
    for pattern, repl in _TECH_CORRECTIONS_ES:
        refined = pattern.sub(repl, refined)
    return refined

_HALLUCINATIONS = {
    ".", "..", "...", "y", "a", "e", "o", "u",
    "you", "thank you.", "thank you", "bye.", "gracias",
    "subtítulos", "subtitulado", "subtítulos por la comunidad de amara.org",
    "suscríbete al canal", "thanks for watching."
}


def _is_repetitive_hallucination(text: str) -> bool:
    """Detecta alucinaciones repetitivas (n-gramas repetidos >=3 veces) o cadenas vacías."""
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) <= 1:
        return True
    lower = stripped.lower()
    if lower in _HALLUCINATIONS:
        return True

    words = re.findall(r"\w+", lower)
    if len(words) >= 6:
        for n in range(1, 6):
            for i in range(len(words) - 3 * n + 1):
                ngram = words[i : i + n]
                if words[i + n : i + 2 * n] == ngram and words[i + 2 * n : i + 3 * n] == ngram:
                    return True
    return False


class LiveMeetingTranscriber:
    def __init__(
        self,
        audio_queue: queue.Queue,
        model_size: str = "base",
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

        try:
            self.vad_model = get_vad_model()
        except Exception:
            self.vad_model = None

        # Coeficientes del filtro pasa-altos 80 Hz para limpiar zumbido eléctrico
        nyq = max(4000.0, self.sample_rate / 2.0)
        self._hp_b, self._hp_a = scipy_signal.butter(2, 80.0 / nyq, btype="highpass")

        # Cola desacoplada para frases consolidadas de ambos canales
        self._transcribe_queue: queue.Queue = queue.Queue(maxsize=32)
        self._last_context: Dict[str, str] = {"mic": "", "pc": ""}
        self._last_emitted_text: Dict[str, str] = {"mic": "", "pc": ""}

        self.is_running = False
        self.is_model_loaded = False
        self._drain_on_stop = False
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

    def _condition_and_normalize_audio(
        self,
        audio: np.ndarray,
        target_peak: float = 0.65,
        max_gain: float = 12.0
    ) -> np.ndarray:
        """Elimina offset DC, ruido sub-80Hz y aplica ganancia adaptativa (AGC) para voces bajas."""
        if len(audio) == 0:
            return audio.astype(np.float32)

        clean = audio.astype(np.float32) - float(np.mean(audio))
        if len(clean) > 16:
            clean = scipy_signal.lfilter(self._hp_b, self._hp_a, clean).astype(np.float32)

        peak = float(np.max(np.abs(clean)))
        if peak > 0.0015:
            p95 = float(np.percentile(np.abs(clean), 95))
            ref_level = max(p95 * 1.5, peak * 0.70, 1e-5)
            gain = min(max_gain, target_peak / ref_level)
            clean = np.clip(clean * gain, -0.95, 0.95).astype(np.float32)
        return clean

    def _get_neural_speech_prob(self, chunk: np.ndarray, channel_peak_est: float) -> float:
        """Calcula probabilidad neuronal de habla humana con Silero VAD v6 (ONNX)."""
        if self.vad_model is None or len(chunk) == 0:
            return 0.0

        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms < 0.0008:
            return 0.0

        chunk_peak = float(np.max(np.abs(chunk)))
        # Ganancia moderada (<= 3.5x) para evitar amplificar música de fondo o respiración sobre el VAD
        gain = min(3.5, 0.25 / max(channel_peak_est, chunk_peak, 0.02))
        amplified = np.clip((chunk.astype(np.float32) - float(np.mean(chunk))) * gain, -0.95, 0.95).astype(np.float32)

        target_len = 1536  # 3 x 512 muestras requeridas por Silero VAD v6 a 16kHz
        if len(amplified) >= target_len:
            vad_in = amplified[:target_len]
        else:
            vad_in = np.pad(amplified, (0, target_len - len(amplified))).astype(np.float32)

        try:
            probs = self.vad_model(vad_in)
            return float(np.max(probs))
        except Exception:
            return 0.0

    @staticmethod
    def _find_best_valley_cut(
        audio: np.ndarray,
        sample_rate: int = 16000,
        search_back_sec: float = 2.0
    ) -> int:
        """
        Busca el valle acústico de menor energía (130ms + 240ms) en la cola del segmento
        para dividir exactamente entre palabras y nunca cortar una sílaba por la mitad.
        """
        n = len(audio)
        margin_end = int(0.14 * sample_rate)
        max_idx = max(1, n - margin_end)
        min_idx = max(int(1.6 * sample_rate), n - int(search_back_sec * sample_rate))
        if min_idx >= max_idx - int(0.1 * sample_rate):
            return n

        w_short = max(1, int(0.13 * sample_rate))
        w_long = max(1, int(0.24 * sample_rate))
        step = max(1, int(0.02 * sample_rate))

        sq = audio[:n].astype(np.float64) ** 2
        cs = np.concatenate(([0.0], np.cumsum(sq)))

        best_cut = n
        min_score = float("inf")
        for center in range(min_idx, max_idx, step):
            s1 = max(0, center - w_short // 2)
            e1 = min(n, center + w_short // 2)
            s2 = max(0, center - w_long // 2)
            e2 = min(n, center + w_long // 2)
            rms_short = (cs[e1] - cs[s1]) / max(1, e1 - s1)
            rms_long = (cs[e2] - cs[s2]) / max(1, e2 - s2)
            score = 0.65 * rms_short + 0.35 * rms_long
            if score < min_score:
                min_score = score
                best_cut = center
        return best_cut

    def initialize_model_async(self, callback: Optional[Callable[[bool, str], None]] = None):
        """Carga el modelo Whisper multilingüe optimizado para CPU (100% offline si está en caché)."""
        def _load():
            try:
                self.update_status(f"Cargando modelo Whisper '{self.model_size}' optimizado para CPU...")
                cores = os.cpu_count() or 4
                threads = min(4, cores)

                if self.vad_model is None:
                    try:
                        self.vad_model = get_vad_model()
                    except Exception:
                        pass

                try:
                    self.whisper_model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=threads,
                        num_workers=1,
                        local_files_only=True
                    )
                except Exception:
                    self.whisper_model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=threads,
                        num_workers=1,
                        local_files_only=False
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
            self._drain_on_stop = False
            self.is_running = True

            self._audio_thread = threading.Thread(target=self._process_audio_loop, daemon=True)
            self._audio_thread.start()

            self._worker_thread = threading.Thread(target=self._transcription_worker_loop, daemon=True)
            self._worker_thread.start()

    def stop(self):
        with self._lock:
            self._drain_on_stop = False
            self.is_running = False

    def flush_and_stop(self, timeout: float = 60.0):
        """Vacía todo el audio en cola, espera la inferencia pendiente y detiene los hilos."""
        with self._lock:
            self._drain_on_stop = True
            self.is_running = False
            audio_t = self._audio_thread
            worker_t = self._worker_thread
        if audio_t is not None and audio_t.is_alive():
            audio_t.join(timeout=min(5.0, timeout))
        if worker_t is not None and worker_t.is_alive():
            worker_t.join(timeout=timeout)

    def reset_session(self):
        """Reinicia el diarizador, contexto y abre una nueva sesión de archivo."""
        self.diarizer.reset()
        self._last_context = {"mic": "", "pc": ""}
        self._last_emitted_text = {"mic": "", "pc": ""}
        if self.logger:
            return self.logger.new_session()
        return None

    def _enqueue_segment(self, full_audio: np.ndarray, src: str, pause_time: float, t_start: float, t_end: float):
        if self._transcribe_queue.full():
            try:
                self._transcribe_queue.get_nowait()
            except queue.Empty:
                pass
        self._transcribe_queue.put((full_audio, src, pause_time, t_start, t_end))

    def _process_audio_loop(self):
        """
        Segmentador continuo por canal independiente impulsado por Silero VAD neuronal:
        Mantiene buffers aislados para 'pc' y 'mic' con pre-roll de 200ms y ganancia adaptativa.
        """
        channels: Dict[str, Dict[str, Any]] = {
            "pc": {
                "buffer": [],
                "pre_roll": deque(maxlen=2),
                "speech_dur": 0.0,
                "silence_dur": 0.0,
                "total_sec": 0.0,
                "start_sec": 0.0,
                "peak_est": 0.05
            },
            "mic": {
                "buffer": [],
                "pre_roll": deque(maxlen=2),
                "speech_dur": 0.0,
                "silence_dur": 0.0,
                "total_sec": 0.0,
                "start_sec": 0.0,
                "peak_est": 0.05
            }
        }

        while self.is_running or (self._drain_on_stop and not self.audio_queue.empty()):
            preset = LATENCY_PRESETS.get(self.latency_mode, LATENCY_PRESETS["ultra_fast"])
            silence_threshold = preset["silence_rms"]
            min_speech = preset["min_speech"]
            max_speech = preset["max_speech"]
            pause_trigger = preset["pause_trigger"]

            try:
                item = self.audio_queue.get(timeout=0.06)
            except queue.Empty:
                if not self.is_running:
                    break
                continue

            if isinstance(item, tuple):
                chunk, source_type = item
            else:
                chunk, source_type = item, "pc"

            src = "mic" if source_type == "mic" else "pc"
            st = channels[src]

            chunk_duration = len(chunk) / self.sample_rate
            st["total_sec"] += chunk_duration

            chunk_peak = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0
            st["peak_est"] = max(chunk_peak, st["peak_est"] * 0.96)
            rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0

            speech_prob = self._get_neural_speech_prob(chunk, st["peak_est"])
            if self.whisper_model is not None and self.is_model_loaded:
                is_speech = (speech_prob >= 0.42)
            else:
                # Permite pruebas unitarias sintéticas (tonos puros) sin modelo Whisper cargado
                is_speech = (speech_prob >= 0.42) or (rms >= silence_threshold)

            if is_speech:
                if not st["buffer"]:
                    pre_list = list(st["pre_roll"])
                    pre_dur = sum(len(c) for c in pre_list) / self.sample_rate
                    st["buffer"].extend(pre_list)
                    st["start_sec"] = max(0.0, st["total_sec"] - chunk_duration - pre_dur)
                    st["pre_roll"].clear()
                st["buffer"].append(chunk)
                st["speech_dur"] += chunk_duration
                st["silence_dur"] = 0.0
            else:
                if st["buffer"]:
                    st["buffer"].append(chunk)
                    st["silence_dur"] += chunk_duration
                    if st["speech_dur"] < min_speech and st["silence_dur"] >= pause_trigger:
                        st["buffer"].clear()
                        st["speech_dur"] = 0.0
                        st["silence_dur"] = 0.0
                else:
                    st["pre_roll"].append(chunk)

            should_transcribe = False
            cut_by_max = False
            if st["speech_dur"] >= min_speech:
                if st["silence_dur"] >= pause_trigger:
                    should_transcribe = True
                elif st["speech_dur"] >= max_speech:
                    should_transcribe = True
                    cut_by_max = True

            if should_transcribe:
                raw_buffer = np.concatenate(st["buffer"])
                pause_time = st["silence_dur"]
                t_start = st["start_sec"]

                if cut_by_max and len(raw_buffer) > int(2.0 * self.sample_rate):
                    cut_idx = self._find_best_valley_cut(raw_buffer, self.sample_rate, search_back_sec=2.0)
                    if 0 < cut_idx < len(raw_buffer) - int(0.10 * self.sample_rate):
                        full_audio = raw_buffer[:cut_idx]
                        carry_over = raw_buffer[cut_idx:].astype(np.float32)
                        carry_dur = len(carry_over) / self.sample_rate
                        t_end = max(t_start, st["total_sec"] - carry_dur)
                        st["buffer"] = [carry_over]
                        st["speech_dur"] = carry_dur
                        st["silence_dur"] = 0.0
                        st["start_sec"] = t_end
                    else:
                        full_audio = raw_buffer
                        t_end = st["total_sec"]
                        st["buffer"] = []
                        st["speech_dur"] = 0.0
                        st["silence_dur"] = 0.0
                else:
                    full_audio = raw_buffer
                    t_end = st["total_sec"]
                    st["buffer"] = []
                    st["speech_dur"] = 0.0
                    st["silence_dur"] = 0.0

                self._enqueue_segment(full_audio, src, pause_time, t_start, t_end)

        # Vaciar cola restante si existe habla residual al detener la sesión
        for src, st in channels.items():
            if st["buffer"] and st["speech_dur"] >= 0.45:
                full_audio = np.concatenate(st["buffer"])
                self._enqueue_segment(full_audio, src, st["silence_dur"], st["start_sec"], st["total_sec"])
                st["buffer"].clear()
                st["speech_dur"] = 0.0

    def _transcription_worker_loop(self):
        """Hilo de inferencia Whisper que consume los fragmentos de audio preparados."""
        while True:
            try:
                item = self._transcribe_queue.get(timeout=0.08)
            except queue.Empty:
                audio_alive = self._audio_thread is not None and self._audio_thread.is_alive()
                if not self.is_running and not audio_alive:
                    break
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
            # 1. Acondicionamiento acústico y AGC antes de inferencia y diarización
            conditioned_audio = self._condition_and_normalize_audio(audio)

            speaker = self.diarizer.identify_speaker(
                conditioned_audio,
                source_type=source_type,
                sample_rate=self.sample_rate,
                pause_duration=pause_duration
            )

            target_lang = None if self.language == "auto" else self.language
            src_key = "mic" if source_type == "mic" else "pc"
            prev_ctx = self._last_context.get(src_key, "")[-140:]
            base_glossary = _TECH_PROMPT_EN if self.language == "en" else _TECH_PROMPT_ES
            prompt_ctx = f"{base_glossary} {prev_ctx}".strip()

            segments, info = self.whisper_model.transcribe(
                conditioned_audio,
                beam_size=2,
                best_of=2,
                language=target_lang,
                initial_prompt=prompt_ctx,
                condition_on_previous_text=False,
                without_timestamps=True,
                temperature=0.0,
                repetition_penalty=1.16,
                no_repeat_ngram_size=3,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.6,
                vad_filter=False
            )

            text_list = []
            logprobs = []
            no_speech_probs = []
            for seg in segments:
                t = seg.text.strip()
                if not t:
                    continue
                if getattr(seg, "compression_ratio", 1.0) > 2.0:
                    continue
                if getattr(seg, "no_speech_prob", 0.0) > 0.75:
                    continue
                if _is_repetitive_hallucination(t):
                    continue
                text_list.append(t)
                logprobs.append(getattr(seg, "avg_logprob", -0.5))
                no_speech_probs.append(getattr(seg, "no_speech_prob", 0.1))

            if not text_list:
                return

            full_text = _refine_technical_text(" ".join(text_list).strip(), self.language)
            if _is_repetitive_hallucination(full_text):
                return
            if full_text.lower() == self._last_emitted_text.get(src_key, "").lower():
                return

            self._last_emitted_text[src_key] = full_text
            mean_logprob = sum(logprobs) / len(logprobs) if logprobs else -1.0
            max_no_speech = max(no_speech_probs) if no_speech_probs else 1.0
            if mean_logprob > -0.85 and max_no_speech < 0.45:
                self._last_context[src_key] = (self._last_context.get(src_key, "") + " " + full_text).strip()[-240:]

            timestamp_str = datetime.now().strftime("%H:%M:%S")

            if self.logger:
                self.logger.log_entry(
                    timestamp_str=timestamp_str,
                    speaker=speaker,
                    text=full_text,
                    start_sec=t_start,
                    end_sec=t_end,
                    source_type=source_type
                )

            if self.on_transcript_ready:
                try:
                    self.on_transcript_ready(timestamp_str, speaker, full_text, source_type, t_start, t_end)
                except TypeError:
                    self.on_transcript_ready(timestamp_str, speaker, full_text, source_type)

        except Exception:
            pass
