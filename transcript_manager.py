"""
Gestor de Transcripción y Registro Continuo Dual (Markdown .md + Timeline .json + .txt).
Mantiene la trazabilidad milimétrica de audio y tiempo relativo de cada interlocutor,
sincroniza con el archivo de audio maestro .wav y anexa la minuta ejecutiva estructurada.
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from meeting_agent import MeetingInsightsAgent

class TranscriptManager:
    def __init__(self, base_dir: str = "reuniones"):
        self.base_dir = os.path.abspath(base_dir)
        self.current_filepath: Optional[str] = None
        self.current_md_path: Optional[str] = None
        self.current_json_path: Optional[str] = None
        self.current_wav_path: Optional[str] = None
        self.current_txt_path: Optional[str] = None
        self.session_id: str = ""
        self.start_iso_time: str = ""

        self._lock = threading.Lock()

        # Registro en memoria estructurado de intervenciones con timestamps relativos
        self.entries: List[Dict[str, Any]] = []
        self._last_speaker: Optional[str] = None
        self._last_time: float = 0.0
        self._is_finalized = False

        self._ensure_dir()
        self._init_session_files()

    def _ensure_dir(self):
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir, exist_ok=True)
            except Exception as e:
                print(f"[ERROR] No se pudo crear carpeta de reuniones: {e}")

    @staticmethod
    def format_offset(seconds: float) -> str:
        """Formatea segundos en MM:SS o HH:MM:SS."""
        secs = int(max(0.0, seconds))
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _init_session_files(self):
        self._ensure_dir()
        self.entries.clear()
        self._is_finalized = False
        self._last_speaker = None
        self._last_time = 0.0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"reunion_{timestamp}"
        self.start_iso_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Nombres de archivos sincronizados de la sesión
        self.current_wav_path = os.path.join(self.base_dir, f"{self.session_id}.wav")
        self.current_md_path = os.path.join(self.base_dir, f"{self.session_id}.md")
        self.current_json_path = os.path.join(self.base_dir, f"{self.session_id}.json")
        self.current_txt_path = os.path.join(self.base_dir, f"{self.session_id}.txt")
        self.current_filepath = self.current_md_path  # Formato principal

        # 1. Encabezado Markdown con Frontmatter YAML estructurado
        md_header = (
            f"---\n"
            f"session_id: \"{self.session_id}\"\n"
            f"date: \"{self.start_iso_time}\"\n"
            f"audio_file: \"{self.session_id}.wav\"\n"
            f"timeline_file: \"{self.session_id}.json\"\n"
            f"type: \"reunion_transcripcion_local\"\n"
            f"status: \"en_grabacion\"\n"
            f"---\n\n"
            f"# 🎙️ Transcripción y Minuta de Reunión Local\n\n"
            f"> **Inicio de sesión:** `{self.start_iso_time}`  \n"
            f"> **Audio sincronizado:** `{self.session_id}.wav`  \n"
            f"> **Privacidad:** `100% Offline / Local en PC (Sin Nube)`\n\n"
            f"---\n\n"
            f"## 💬 Registro de Diálogo en Tiempo Real\n\n"
        )
        try:
            with open(self.current_md_path, "w", encoding="utf-8") as f:
                f.write(md_header)
        except Exception as e:
            print(f"[ERROR] Al inicializar archivo .md de reunión: {e}")

        # 2. Encabezado legacy .txt
        sep = "=" * 76
        txt_header = (
            f"{sep}\n"
            f"   ASISTENTE DE REUNIÓN LOCAL - TRANSCRIPCIÓN Y NOTAS CONFIDENCIALES\n"
            f"   Inicio de sesión: {self.start_iso_time}\n"
            f"   Archivo de Audio: {self.session_id}.wav\n"
            f"   Modo: 100% Offline / Privado (Local en PC)\n"
            f"{sep}\n\n"
        )
        try:
            with open(self.current_txt_path, "w", encoding="utf-8") as f:
                f.write(txt_header)
        except Exception as e:
            print(f"[ERROR] Al inicializar archivo .txt de reunión: {e}")

    def log_entry(
        self,
        timestamp_str: str,
        speaker: str,
        text: str,
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        source_type: str = "pc"
    ):
        """
        Registra una intervención con doble trazabilidad:
        1. Desplazamiento relativo respecto al audio [MM:SS -> MM:SS] (para el reproductor/frontend).
        2. Hora del reloj de pared [HH:MM:SS].
        """
        if not text or not text.strip():
            return
        clean_text = text.strip()

        with self._lock:
            start_fmt = self.format_offset(start_sec)
            end_fmt = self.format_offset(end_sec)
            time_range_str = f"{start_fmt} ➔ {end_fmt}"

            # 1. Guardar en memoria estructurada (para JSON y Agente)
            entry_obj = {
                "id": len(self.entries) + 1,
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "time_range": time_range_str,
                "clock_time": timestamp_str,
                "speaker": speaker,
                "source": source_type,
                "text": clean_text
            }
            self.entries.append(entry_obj)

            # Icono distintivo por canal
            speaker_icon = "🎙️" if source_type == "mic" else "🔊"

            # 2. Formato Markdown enriquecido
            now = time.time()
            if self._last_speaker == speaker and (now - self._last_time < 4.0):
                md_entry = f"> {clean_text}\n>\n"
                txt_entry = f"{clean_text}\n\n"
            else:
                md_entry = f"> **[{time_range_str}] {speaker_icon} {speaker}:**  \n> {clean_text}\n>\n"
                txt_entry = f"[{time_range_str}] [{timestamp_str}] [{speaker}]\n{clean_text}\n\n"
                self._last_speaker = speaker

            self._last_time = now

            if not self.current_md_path or not os.path.exists(self.current_md_path):
                self._init_session_files()

            # Escribir en Markdown (.md)
            try:
                with open(self.current_md_path, "a", encoding="utf-8") as f:
                    f.write(md_entry)
                    f.flush()
            except Exception as e:
                print(f"[ERROR] Al escribir en archivo Markdown de reunión: {e}")

            # Escribir en Legacy TXT (.txt)
            try:
                with open(self.current_txt_path, "a", encoding="utf-8") as f:
                    f.write(txt_entry)
                    f.flush()
            except Exception as e:
                print(f"[ERROR] Al escribir en archivo TXT de reunión: {e}")

    def finalize_meeting(
        self,
        agent: MeetingInsightsAgent,
        audio_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Ejecuta el agente de compromisos, guarda el timeline completo en JSON
        y anexa la minuta ejecutiva tanto al .md como al .txt.
        """
        with self._lock:
            if not self.current_md_path or not os.path.exists(self.current_md_path):
                self._init_session_files()

            # 1. Generar reporte mediante el agente de compromisos
            report = agent.generate_meeting_report(self.entries)

            summary_md = agent.format_for_markdown(report)
            summary_txt = agent.format_for_txt(report)

            duration_sec = audio_metadata.get("duration_seconds", 0.0) if audio_metadata else 0.0
            duration_fmt = audio_metadata.get("duration_formatted", "00:00:00") if audio_metadata else "00:00:00"

            # 2. Anexar al archivo Markdown (.md)
            try:
                with open(self.current_md_path, "a", encoding="utf-8") as f:
                    f.write(summary_md)
                    f.flush()
            except Exception as e:
                print(f"[ERROR] Al anexar minuta al archivo .md: {e}")

            # 3. Anexar al archivo .txt
            try:
                with open(self.current_txt_path, "a", encoding="utf-8") as f:
                    f.write(summary_txt)
                    f.flush()
            except Exception as e:
                print(f"[ERROR] Al anexar minuta al archivo .txt: {e}")

            # 4. Guardar archivo JSON maestro sincronizado para el futuro Frontend
            distinct_speakers = sorted(list(set(e["speaker"] for e in self.entries if e.get("speaker"))))
            json_payload = {
                "session_id": self.session_id,
                "title": "Sesión de Trabajo y Reunión Local",
                "date": self.start_iso_time,
                "audio_file": os.path.basename(self.current_wav_path) if self.current_wav_path else "",
                "markdown_file": os.path.basename(self.current_md_path) if self.current_md_path else "",
                "duration_seconds": duration_sec,
                "duration_formatted": duration_fmt,
                "speakers": distinct_speakers,
                "total_segments": len(self.entries),
                "segments": self.entries,
                "summary": report
            }

            try:
                with open(self.current_json_path, "w", encoding="utf-8") as f:
                    json.dump(json_payload, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[ERROR] Al guardar archivo JSON sincronizado: {e}")

            self._is_finalized = True
            return (self.current_md_path, report)

    def new_session(self) -> str:
        """Cierra la sesión anterior e inicia una nueva reunión limpia."""
        with self._lock:
            self._init_session_files()
            return self.current_md_path

    def get_current_filepath(self) -> Optional[str]:
        return self.current_md_path or self.current_filepath

    def get_current_wav_path(self) -> Optional[str]:
        return self.current_wav_path

    def get_current_json_path(self) -> Optional[str]:
        return self.current_json_path

    def get_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.entries)

    def is_finalized(self) -> bool:
        return self._is_finalized

    def open_current_file(self):
        """Abre el archivo Markdown (.md) de la reunión actual."""
        target = self.current_md_path or self.current_filepath
        if target and os.path.exists(target):
            try:
                os.startfile(target)
            except Exception as e:
                print(f"[ERROR] Al abrir archivo de reunión: {e}")

    def open_current_audio(self):
        """Abre el archivo de audio (.wav) en el reproductor de Windows."""
        if self.current_wav_path and os.path.exists(self.current_wav_path):
            try:
                os.startfile(self.current_wav_path)
            except Exception as e:
                print(f"[ERROR] Al abrir audio de reunión: {e}")

    def open_folder(self):
        """Abre la carpeta de reuniones en el Explorador de Windows."""
        self._ensure_dir()
        try:
            os.startfile(self.base_dir)
        except Exception as e:
            print(f"[ERROR] Al abrir carpeta de reuniones: {e}")
