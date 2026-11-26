"""
Motor de Diarización e Identificación de Hablantes (100% Local en CPU).
Diferencia interlocutores de forma estable con histeresis anti-fragmentación.

Capacidades:
1. Micrófono local: por defecto asigna al usuario ('Tú'); si multi_local_mode=True,
   diferencia múltiples voces en sala ([Tú], [Local 2], etc.).
2. Audio remoto del PC (Teams/Meet/Zoom): diferencia [Participante 1], [Participante 2]
   con inercia temporal para no dividir a un mismo locutor en decenas de perfiles falsos.
"""

import numpy as np
from scipy.fftpack import dct
from typing import Dict, Optional, List


class MeetingSpeakerDiarizer:
    def __init__(
        self,
        user_label: str = "Tú",
        max_speakers: int = 10,
        similarity_threshold: float = 0.70,
        multi_local_mode: bool = False
    ):
        self.user_label = user_label
        self.max_speakers = max_speakers
        self.similarity_threshold = similarity_threshold
        self.multi_local_mode = multi_local_mode

        # Hablantes frente al micrófono local
        self.local_speakers: Dict[int, Dict] = {}
        self.last_local_id: int = 1
        self.next_local_id: int = 1
        self._local_divergent_streak: int = 0

        # Hablantes remotos del PC (WASAPI Loopback)
        self.remote_speakers: Dict[int, Dict] = {}
        self.last_remote_id: int = 1
        self.next_remote_id: int = 1
        self._remote_divergent_streak: int = 0

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
        self._local_divergent_streak = 0

        self.remote_speakers.clear()
        self.last_remote_id = 1
        self.next_remote_id = 1
        self._remote_divergent_streak = 0

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
        """Extrae un vector acústico normalizado (MFCC 1..12 + tono fundamental F0)."""
        if len(audio) < int(sample_rate * 0.35):
            return None

        samples = audio.astype(np.float32)
        samples = samples - np.mean(samples)
        rms = np.sqrt(np.mean(samples ** 2))
        if rms < 1e-4:
            return None

        if len(samples) > 24000:
            analysis_samples = samples[:24000]
        else:
            analysis_samples = samples

        n_samples = len(analysis_samples)
        window = np.hamming(n_samples)
        fft_vals = np.abs(np.fft.rfft(analysis_samples * window))

        fb = self._get_mel_filterbank(len(fft_vals), sample_rate)
        mel_energies = np.dot(fb, fft_vals) + 1e-6
        log_energies = np.log(mel_energies)
        mfcc = dct(log_energies, type=2, norm='ortho')[1:self.n_mfcc]

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

        f0_feature = (np.log(max(50.0, min(500.0, f0_estimate))) - 5.0) * 15.0

        vec = np.concatenate([mfcc, [f0_feature]], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-6:
            vec = vec / norm
        return vec

    def _cluster_speaker(
        self,
        voiceprint: Optional[np.ndarray],
        audio_len: int,
        sample_rate: int,
        speakers_dict: Dict[int, Dict],
        is_mic: bool,
        pause_duration: float
    ) -> str:
        last_id = self.last_local_id if is_mic else self.last_remote_id

        if voiceprint is None:
            if speakers_dict and last_id in speakers_dict:
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
                self._local_divergent_streak = 0
            else:
                self.last_remote_id = 1
                self.next_remote_id = 2
                self._remote_divergent_streak = 0

            self.last_speaker_name = first_name
            return first_name

        best_id = None
        best_sim = -1.0
        for spk_id, spk_data in speakers_dict.items():
            sim = float(np.dot(voiceprint, spk_data["centroid"]))
            if sim > best_sim:
                best_sim = sim
                best_id = spk_id

        # Coincide con hablante conocido
        active_threshold = 0.85 if (is_mic and self.multi_local_mode) else self.similarity_threshold
        if best_sim >= active_threshold and best_id is not None:
            spk = speakers_dict[best_id]
            alpha = min(0.2, 1.0 / (spk["count"] + 1))
            new_centroid = (1.0 - alpha) * spk["centroid"] + alpha * voiceprint
            new_norm = np.linalg.norm(new_centroid)
            if new_norm > 1e-6:
                spk["centroid"] = new_centroid / new_norm
            spk["count"] += 1

            if is_mic:
                self.last_local_id = best_id
                self._local_divergent_streak = 0
            else:
                self.last_remote_id = best_id
                self._remote_divergent_streak = 0

            self.last_speaker_name = spk["name"]
            return spk["name"]

        # Histeresis e inercia para canal remoto ('pc') para evitar falsos Participante 2..10
        if not is_mic:
            self._remote_divergent_streak += 1
            is_long_clear_turn = (audio_len >= sample_rate * 1.5) and (pause_duration >= 0.65)
            allow_new = is_long_clear_turn and (self._remote_divergent_streak >= 2) and (best_sim < 0.58)
            if not allow_new:
                fallback_spk = speakers_dict.get(last_id) or speakers_dict.get(1)
                self.last_speaker_name = fallback_spk["name"]
                return fallback_spk["name"]
            self._remote_divergent_streak = 0

        # Nuevo hablante confirmado
        if is_mic:
            new_id = self.next_local_id
            if len(speakers_dict) < self.max_speakers:
                self.next_local_id += 1
            else:
                new_id = max(1, (self.last_local_id % self.max_speakers) + 1)
            new_name = f"Local {new_id}"
            self.last_local_id = new_id
            self._local_divergent_streak = 0
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
        Determina quién está hablando:
        - Si viene del micrófono y multi_local_mode=False: asigna siempre al usuario ('Tú').
        - Si viene del PC: aplica clustering con inercia entre Participante 1, Participante 2, etc.
        """
        is_mic = (source_type == "mic")
        if is_mic and not self.multi_local_mode:
            if 1 not in self.local_speakers:
                self.local_speakers[1] = {"name": self.user_label, "centroid": np.zeros(13, dtype=np.float32), "count": 1}
            self.last_speaker_name = self.user_label
            return self.user_label

        voiceprint = self.extract_voiceprint(audio, sample_rate)
        target_dict = self.local_speakers if is_mic else self.remote_speakers
        return self._cluster_speaker(
            voiceprint=voiceprint,
            audio_len=len(audio),
            sample_rate=sample_rate,
            speakers_dict=target_dict,
            is_mic=is_mic,
            pause_duration=pause_duration
        )
