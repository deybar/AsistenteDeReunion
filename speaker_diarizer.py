"""
Motor de Diarización e Identificación de Hablantes (100% Local en CPU).
Diferencia interlocutores incluso si comparten el mismo micrófono físico o el mismo canal de audio.

Capacidades:
1. Diarización Multilocutor en Micrófono: Si dos o más personas hablan frente al mismo PC,
   analiza la huella acústica (MFCC + tono F0) para distinguir [Tú], [Local 2], [Local 3], etc.
2. Diarización Multilocutor Remoto: Para las voces provenientes del PC (Teams/Meet/Zoom),
   distingue [Participante 1], [Participante 2], etc.
3. Aislamiento de canales: Mantiene separados los perfiles locales de los remotos para evitar
   que el eco confunda las identidades.
"""

import numpy as np
from scipy.fftpack import dct
from typing import Dict, Optional, List

class MeetingSpeakerDiarizer:
    def __init__(
        self,
        user_label: str = "Tú",
        max_speakers: int = 10,
        similarity_threshold: float = 0.88
    ):
        self.user_label = user_label
        self.max_speakers = max_speakers
        self.similarity_threshold = similarity_threshold

        # Hablantes frente al micrófono local
        self.local_speakers: Dict[int, Dict] = {}
        self.last_local_id: int = 1
        self.next_local_id: int = 1

        # Hablantes remotos del PC (WASAPI Loopback)
        self.remote_speakers: Dict[int, Dict] = {}
        self.last_remote_id: int = 1
        self.next_remote_id: int = 1

        self.last_speaker_name: str = self.user_label

        # Precomputar banco de filtros Mel (20 filtros triangulares de 100 Hz a 7500 Hz)
        self.sample_rate = 16000
        self.n_mels = 20
        self.n_mfcc = 13
        self._filterbank = None
        self._filterbank_freqs_len = 0

    def reset(self):
        """Reinicia los perfiles de todos los interlocutores para una nueva reunión."""
        self.local_speakers.clear()
        self.last_local_id = 1
        self.next_local_id = 1

        self.remote_speakers.clear()
        self.last_remote_id = 1
        self.next_remote_id = 1

        self.last_speaker_name = self.user_label

    def set_user_label(self, label: str):
        self.user_label = label.strip() or "Tú"
        if 1 in self.local_speakers:
            self.local_speakers[1]["name"] = self.user_label

    def get_known_speakers(self) -> List[str]:
        names = []
        for spk in self.local_speakers.values():
            if spk["name"] not in names:
                names.append(spk["name"])
        for spk in self.remote_speakers.values():
            if spk["name"] not in names:
                names.append(spk["name"])
        if not names:
            names.append(self.user_label)
        return names

    def _get_mel_filterbank(self, n_freqs: int, sample_rate: int) -> np.ndarray:
        if self._filterbank is not None and self._filterbank_freqs_len == n_freqs:
            return self._filterbank

        freqs = np.fft.rfftfreq((n_freqs - 1) * 2, 1.0 / sample_rate)
        low_mel = 2595.0 * np.log10(1.0 + 100.0 / 700.0)
        high_mel = 2595.0 * np.log10(1.0 + 7500.0 / 700.0)
        mel_points = np.linspace(low_mel, high_mel, self.n_mels + 2)
        hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)

        fb = np.zeros((self.n_mels, len(freqs)), dtype=np.float32)
        for i in range(self.n_mels):
            left, center, right = hz_points[i], hz_points[i + 1], hz_points[i + 2]
            fb[i] = np.maximum(0.0, np.minimum(
                (freqs - left) / (center - left + 1e-6),
                (right - freqs) / (right - center + 1e-6)
            ))

        self._filterbank = fb
        self._filterbank_freqs_len = len(freqs)
        return self._filterbank

    def extract_voiceprint(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        Extrae un vector acústico representativo del tracto vocal y cuerdas vocales:
        - Coeficientes Cepstrales en Escala Mel (MFCC 1..12): forma del tracto vocal
        - F0 (Tono vocal fundamental por autocorrelación): tono biológico de las cuerdas vocales
        Inferencia ultra-ligera en CPU (< 3 ms).
        """
        if len(audio) < int(sample_rate * 0.35):
            return None

        samples = audio.astype(np.float32)
        samples = samples - np.mean(samples)
        rms = np.sqrt(np.mean(samples ** 2))
        if rms < 1e-4:
            return None

        # Usar segmento representativo de hasta 1.5s
        if len(samples) > 24000:
            analysis_samples = samples[:24000]
        else:
            analysis_samples = samples

        n_samples = len(analysis_samples)
        window = np.hamming(n_samples)
        fft_vals = np.abs(np.fft.rfft(analysis_samples * window))

        # 1. Banco de filtros Mel y MFCC (coeficientes 1 a 12, omitiendo 0 para independizar del volumen)
        fb = self._get_mel_filterbank(len(fft_vals), sample_rate)
        mel_energies = np.dot(fb, fft_vals) + 1e-6
        log_energies = np.log(mel_energies)
        mfcc = dct(log_energies, type=2, norm='ortho')[1:self.n_mfcc]

        # 2. Estimación de Pitch (F0) por autocorrelación
        if len(samples) > 2048:
            mid = len(samples) // 2
            pitch_samples = samples[mid - 1024 : mid + 1024]
        else:
            pitch_samples = samples

        corr = np.correlate(pitch_samples, pitch_samples, mode='full')
        corr = corr[len(corr) // 2 :]
        min_lag = int(sample_rate / 400)
        max_lag = int(sample_rate / 60)
        if len(corr) > max_lag:
            pitch_lag = min_lag + np.argmax(corr[min_lag:max_lag])
            f0_estimate = sample_rate / max(1, pitch_lag)
        else:
            f0_estimate = 150.0

        # Normalizar log(f0) centrado en rango vocal medio humano
        f0_feature = (np.log(max(50.0, min(500.0, f0_estimate))) - 5.0) * 15.0

        # Vector final combinado tracto vocal + tono
        vec = np.concatenate([mfcc, [f0_feature]], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def _cluster_speaker(
        self,
        voiceprint: Optional[np.ndarray],
        speakers_dict: Dict[int, Dict],
        is_mic: bool,
        pause_duration: float
    ) -> str:
        last_id = self.last_local_id if is_mic else self.last_remote_id

        # Audio muy corto
        if voiceprint is None:
            if pause_duration < 1.2 and speakers_dict and last_id in speakers_dict:
                name = speakers_dict[last_id]["name"]
                self.last_speaker_name = name
                return name
            default_name = self.user_label if is_mic else f"Participante {last_id}"
            self.last_speaker_name = default_name
            return default_name

        # Primer hablante en este canal
        if not speakers_dict:
            first_name = self.user_label if is_mic else "Participante 1"
            speakers_dict[1] = {
                "name": first_name,
                "centroid": voiceprint,
                "count": 1
            }
            if is_mic:
                self.last_local_id = 1
                self.next_local_id = 2
            else:
                self.last_remote_id = 1
                self.next_remote_id = 2

            self.last_speaker_name = first_name
            return first_name

        # Similitud coseno contra hablantes registrados
        best_id = None
        best_sim = -1.0
        for spk_id, spk_data in speakers_dict.items():
            sim = float(np.dot(voiceprint, spk_data["centroid"]))
            if sim > best_sim:
                best_sim = sim
                best_id = spk_id

        # Coincide con hablante conocido
        if best_sim >= self.similarity_threshold and best_id is not None:
            spk = speakers_dict[best_id]
            alpha = min(0.2, 1.0 / (spk["count"] + 1))
            new_centroid = (1.0 - alpha) * spk["centroid"] + alpha * voiceprint
            new_norm = np.linalg.norm(new_centroid)
            if new_norm > 1e-6:
                spk["centroid"] = new_centroid / new_norm
            spk["count"] += 1

            if is_mic:
                self.last_local_id = best_id
            else:
                self.last_remote_id = best_id

            self.last_speaker_name = spk["name"]
            return spk["name"]

        # Nuevo hablante detectado en el mismo canal
        if is_mic:
            new_id = self.next_local_id
            if len(speakers_dict) < self.max_speakers:
                self.next_local_id += 1
            else:
                new_id = max(1, (self.last_local_id % self.max_speakers) + 1)
            new_name = f"Local {new_id}"
            self.last_local_id = new_id
        else:
            new_id = self.next_remote_id
            if len(speakers_dict) < self.max_speakers:
                self.next_remote_id += 1
            else:
                new_id = max(1, (self.last_remote_id % self.max_speakers) + 1)
            new_name = f"Participante {new_id}"
            self.last_remote_id = new_id

        speakers_dict[new_id] = {
            "name": new_name,
            "centroid": voiceprint,
            "count": 1
        }
        self.last_speaker_name = new_name
        return new_name

    def identify_speaker(
        self,
        audio: np.ndarray,
        source_type: str = "pc",
        sample_rate: int = 16000,
        pause_duration: float = 0.0
    ) -> str:
        """
        Determina quién está hablando analizando la huella acústica vocal (MFCC + Pitch F0).
        - Si viene del micrófono: distingue entre 'Tú' y otras personas presentes en la misma sala ('Local 2', 'Local 3').
        - Si viene del PC: distingue 'Participante 1', 'Participante 2', etc.
        """
        voiceprint = self.extract_voiceprint(audio, sample_rate)
        is_mic = (source_type == "mic")
        target_dict = self.local_speakers if is_mic else self.remote_speakers
        return self._cluster_speaker(voiceprint, target_dict, is_mic=is_mic, pause_duration=pause_duration)
