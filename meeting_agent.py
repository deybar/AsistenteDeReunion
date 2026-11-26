"""
Agente Inteligente de Reuniones (100% Local y Confidencial).
Analiza las conversaciones transcritas para extraer:
1. Resumen general de la reunión
2. Compromisos adquiridos y tareas asignadas por interlocutor (Action Items)
3. Temas clave para estudiar, revisar o investigar (desarrollo y equipo)
4. Acuerdos técnicos y decisiones tomadas
5. Próximos pasos

Arquitectura Híbrida:
- Nivel 1: Motor Semántico y Heurístico Local (Offline, instantáneo, cero dependencias)
- Nivel 2: LLM Local Opcional (Ollama en localhost:11434 si está instalado)
"""

import os
import re
import json
import time
import subprocess
from typing import List, Dict, Any, Optional
import requests


class MeetingInsightsAgent:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:3b",
        ollama_enabled: bool = True
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.ollama_enabled = ollama_enabled
        self._ollama_start_attempted = False

    def _try_start_ollama_service(self) -> bool:
        """Intenta iniciar el servicio local de Ollama en segundo plano si está instalado."""
        if self._ollama_start_attempted:
            return False
        self._ollama_start_attempted = True

        local_app = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            os.path.join(local_app, "Programs", "Ollama", "ollama.exe") if local_app else "",
            r"C:\Program Files\Ollama\ollama.exe"
        ]
        ollama_exe = next((p for p in candidates if p and os.path.exists(p)), None)
        if not ollama_exe:
            return False

        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [ollama_exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                close_fds=True
            )
            for _ in range(5):
                time.sleep(0.5)
                try:
                    resp = requests.get(f"{self.ollama_url}/api/tags", timeout=0.8)
                    if resp.status_code == 200:
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _select_available_model(self, models_payload: List[Dict[str, Any]]):
        """Selecciona el modelo configurado o el mejor modelo chat/instruct instalado."""
        names = [m.get("name", "") for m in models_payload if m.get("name")]
        if not names:
            return

        if self.ollama_model in names:
            return

        base_target = self.ollama_model.split(":")[0].lower()
        for name in names:
            if name.lower().startswith(base_target):
                self.ollama_model = name
                return

        preferred_prefixes = ("qwen2.5", "llama3.2", "llama3", "mistral", "gemma", "phi")
        for pref in preferred_prefixes:
            for name in names:
                if pref in name.lower():
                    self.ollama_model = name
                    return

        self.ollama_model = names[0]

    def is_ollama_available(self) -> bool:
        """Verifica si Ollama está activo; si está instalado pero apagado, intenta levantarlo."""
        if not self.ollama_enabled:
            return False
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=1.2)
            if resp.status_code == 200:
                self._select_available_model(resp.json().get("models", []))
                return True
        except Exception:
            if self._try_start_ollama_service():
                try:
                    resp = requests.get(f"{self.ollama_url}/api/tags", timeout=1.2)
                    if resp.status_code == 200:
                        self._select_available_model(resp.json().get("models", []))
                        return True
                except Exception:
                    pass
        return False

    def generate_meeting_report(self, entries: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Punto de entrada principal:
        Recibe la lista de intervenciones [{'time': 'HH:MM:SS', 'speaker': '...', 'text': '...'}]
        y retorna el análisis estructurado.
        """
        if not entries:
            return {
                "summary": "No se registraron intervenciones durante la sesión.",
                "commitments": [],
                "study_topics": [],
                "decisions": [],
                "next_steps": [],
                "source": "heuristic"
            }

        # Intentar con Ollama si está activo localmente
        if self.is_ollama_available():
            try:
                llm_result = self._generate_with_ollama(entries)
                if llm_result:
                    return llm_result
            except Exception:
                pass

        # Fallback instantáneo y robusto: Motor Semántico Heurístico Local
        return self._generate_with_heuristics(entries)

    # =========================================================================
    # MOTOR SEMÁNTICO Y HEURÍSTICO LOCAL (100% OFFLINE)
    # =========================================================================
    def _generate_with_heuristics(self, entries: List[Dict[str, str]]) -> Dict[str, Any]:
        commitments: List[Dict[str, str]] = []
        study_topics: List[Dict[str, str]] = []
        decisions: List[Dict[str, str]] = []
        topics_seen = set()

        # Patrones lingüísticos mejorados en Español e Inglés
        re_study = re.compile(
            r"\b(?:es\s+importante\s+que|debes?|tienes?\s+que|hay\s+que|necesitamos?|deberías?|"
            r"sugiero|recomiendo|toca|vale\s+la\s+pena|importante\s+que|convendría|"
            r"you\s+should|you\s+need\s+to|must|have\s+to|make\s+sure\s+to|let's)\s+"
            r"(estudi(?:ar|es|en|emos)?|revis(?:ar|es|en|emos)?|investig(?:ar|ues|uen|uemos)?|"
            r"analiz(?:ar|es|en|emos)?|cheque(?:ar|es|en|emos)?|le(?:er|as|an|amos)?|"
            r"prob(?:ar|es|en|emos)?|document(?:ar|es|en|emos)?|"
            r"study|review|research|investigate|read|check|test|analyze)\s+"
            r"((?:[0-9]+\.[0-9]+|[^.,;!?\n])+)",
            re.IGNORECASE
        )

        re_self_commit = re.compile(
            r"\b(?:yo\s+(?:me\s+encargo|voy\s+a|puedo|me\s+comprometo|hago|subo|creo|preparo|reviso|investigo)|"
            r"me\s+encargo\s+de|quedo\s+pendiente\s+de|me\s+comprometo\s+a|cuenten\s+con|"
            r"i\s+will|i'll|i\s+can|i'm\s+going\s+to|i\s+take\s+care\s+of)\s+"
            r"((?:[0-9]+\.[0-9]+|[^.,;!?\n])+)",
            re.IGNORECASE
        )

        re_assigned_commit = re.compile(
            r"\b(?:te\s+encargas\s+de|quedás?\s+a\s+cargo\s+de|puedes\s+hacer|podrías\s+revisar|encárgate\s+de|"
            r"can\s+you|could\s+you|please\s+take\s+care\s+of|assigned\s+to)\s+"
            r"((?:[0-9]+\.[0-9]+|[^.,;!?\n])+)",
            re.IGNORECASE
        )

        re_decision = re.compile(
            r"\b(?:quedamos\s+en\s+que|acordamos(?:\s+que)?|la\s+decisión\s+es|se\s+decide|definimos\s+que|"
            r"vamos\s+a\s+usar|elegimos|descartamos|aprobado|we\s+agreed|decided\s+to|decision\s+is)\s+"
            r"((?:[0-9]+\.[0-9]+|[^.,;!?\n])+)",
            re.IGNORECASE
        )

        re_timeframe = re.compile(
            r"\b(mañana|hoy|para el|el lunes|el martes|el miércoles|el jueves|el viernes|"
            r"la próxima semana|esta tarde|al final del día|fin de semana|"
            r"tomorrow|today|by friday|next week|end of day)\b",
            re.IGNORECASE
        )

        total_words = 0
        speakers_participating = set()
        substantive_turns = []

        for item in entries:
            time_str = item.get("time") or item.get("clock_time") or item.get("time_range") or ""
            speaker = item.get("speaker", "Interlocutor")
            text = item.get("text", "").strip()
            if not text:
                continue

            speakers_participating.add(speaker)
            word_count = len(text.split())
            total_words += word_count
            if word_count >= 6:
                substantive_turns.append((word_count, speaker, time_str, text))

            # 1. Detectar temas a estudiar / investigar / revisar
            for m in re_study.finditer(text):
                action_verb = m.group(1).strip().capitalize()
                raw_topic = m.group(2).strip()
                topic_clean = re.split(r"\b(y\s+luego|porque|ya\s+que|para\s+que)\b", raw_topic, flags=re.IGNORECASE)[0].strip()
                if len(topic_clean) > 4:
                    key = f"{action_verb.lower()}_{topic_clean.lower()}"
                    if key not in topics_seen:
                        topics_seen.add(key)
                        study_topics.append({
                            "time": time_str,
                            "speaker": speaker,
                            "topic": f"{action_verb} {topic_clean}"
                        })

            # 2. Detectar auto-compromisos ("yo voy a...", "me encargo de...", "I will...")
            for m in re_self_commit.finditer(text):
                task = m.group(1).strip()
                task = re.sub(r"^(?:de|que)\s+", "", task, flags=re.IGNORECASE).strip()
                tf_match = re_timeframe.search(text)
                timeframe = tf_match.group(0).lower() if tf_match else ""
                full_task = task.capitalize()
                if timeframe and timeframe not in full_task.lower():
                    full_task += f" ({timeframe})"

                if len(task) > 5:
                    commitments.append({
                        "time": time_str,
                        "assignee": speaker,
                        "task": full_task
                    })

            # 3. Detectar asignaciones a terceros
            for m in re_assigned_commit.finditer(text):
                task = m.group(1).strip()
                task = re.sub(r"^(?:de|que)\s+", "", task, flags=re.IGNORECASE).strip()
                if len(task) > 5:
                    commitments.append({
                        "time": time_str,
                        "assignee": "Equipo / Asignado",
                        "task": task.capitalize()
                    })

            # 4. Detectar acuerdos y decisiones
            for m in re_decision.finditer(text):
                dec = m.group(1).strip()
                dec = re.sub(r"^(?:de|que)\s+", "", dec, flags=re.IGNORECASE).strip()
                if len(dec) > 5:
                    decisions.append({
                        "time": time_str,
                        "decision": dec.capitalize()
                    })

        # Resumen general de la conversación con puntos destacados
        spk_list = ", ".join(sorted(speakers_participating)) if speakers_participating else "Participantes"
        summary_lines = [
            f"Sesión con {len(speakers_participating)} interlocutor(es) activo(s) ({spk_list}) "
            f"con un total de {len(entries)} intervenciones registradas ({total_words} palabras)."
        ]
        if substantive_turns:
            top_highlights = sorted(substantive_turns, key=lambda x: x[0], reverse=True)[:3]
            summary_lines.append("Puntos destacados:")
            for _, spk, t_str, txt in top_highlights:
                snippet = txt if len(txt) <= 140 else txt[:137] + "..."
                t_prefix = f"[{t_str}] " if t_str else ""
                summary_lines.append(f"- {t_prefix}{spk}: {snippet}")
        summary_intro = "\n".join(summary_lines)

        # Próximos pasos deducidos de los compromisos
        next_steps = []
        for c in commitments[:5]:
            next_steps.append(f"{c['assignee']}: {c['task']}")
        if not next_steps and study_topics:
            for s in study_topics[:3]:
                next_steps.append(f"{s['topic']} (mencionado por {s['speaker']})")

        return {
            "summary": summary_intro,
            "commitments": commitments,
            "study_topics": study_topics,
            "decisions": decisions,
            "next_steps": next_steps,
            "source": "heuristic"
        }

    # =========================================================================
    # MOTOR LLM LOCAL CON OLLAMA (OPCIONAL EN LOCALHOST)
    # =========================================================================
    @staticmethod
    def _normalize_llm_report(parsed: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Normaliza la estructura JSON devuelta por el LLM para evitar fallos en UI/Markdown."""
        norm_commitments = []
        for c in parsed.get("commitments", []) or []:
            if isinstance(c, dict):
                norm_commitments.append({
                    "assignee": str(c.get("assignee") or c.get("responsable") or "Participante"),
                    "task": str(c.get("task") or c.get("action") or c.get("description") or ""),
                    "time": str(c.get("time") or "")
                })
            elif isinstance(c, str) and c.strip():
                norm_commitments.append({"assignee": "Participante", "task": c.strip(), "time": ""})

        norm_topics = []
        for s in parsed.get("study_topics", []) or []:
            if isinstance(s, dict):
                norm_topics.append({
                    "topic": str(s.get("topic") or s.get("tema") or ""),
                    "speaker": str(s.get("speaker") or "")
                })
            elif isinstance(s, str) and s.strip():
                norm_topics.append({"topic": s.strip(), "speaker": ""})

        norm_decisions = []
        for d in parsed.get("decisions", []) or []:
            if isinstance(d, dict):
                val = d.get("decision") or d.get("text") or ""
                if str(val).strip():
                    norm_decisions.append({"decision": str(val).strip(), "time": str(d.get("time") or "")})
            elif isinstance(d, str) and d.strip():
                norm_decisions.append({"decision": d.strip(), "time": ""})

        norm_steps = []
        for st in parsed.get("next_steps", []) or []:
            if isinstance(st, dict):
                norm_steps.append(str(st.get("step") or st.get("task") or st.get("description") or st))
            elif isinstance(st, str) and st.strip():
                norm_steps.append(st.strip())

        return {
            "summary": str(parsed.get("summary") or "Resumen generado por IA local."),
            "commitments": [c for c in norm_commitments if c["task"]],
            "study_topics": [t for t in norm_topics if t["topic"]],
            "decisions": norm_decisions,
            "next_steps": norm_steps,
            "source": f"ollama ({model_name})"
        }

    def _generate_with_ollama(self, entries: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        lines = []
        for e in entries:
            t_val = e.get("time") or e.get("clock_time") or e.get("time_range") or ""
            lines.append(f"[{t_val}] {e.get('speaker', '')}: {e.get('text', '')}")
        transcript_text = "\n".join(lines)
        if len(transcript_text) > 4500:
            transcript_text = transcript_text[-4500:]

        prompt = (
            "Eres un Asistente Ejecutivo Senior de Ingeniería y Análisis de Reuniones. "
            "A continuación tienes la transcripción automática (ASR) de una reunión o sesión técnica.\n"
            "Deduce el significado real usando el contexto completo incluso si hay pequeños errores fonéticos.\n\n"
            f"--- TRANSCRIPCIÓN ---\n{transcript_text}\n--- FIN TRANSCRIPCIÓN ---\n\n"
            "Genera un JSON estrictamente válido en español con estas claves:\n"
            "{\n"
            '  "summary": "Resumen ejecutivo claro (3 a 5 líneas) explicando objetivo, temas y conclusiones",\n'
            '  "commitments": [{"assignee": "Responsable", "task": "Acción concreta", "time": "HH:MM:SS"}],\n'
            '  "study_topics": [{"topic": "Tema técnico o concepto clave para investigar/revisar", "speaker": "Quién lo mencionó"}],\n'
            '  "decisions": ["Acuerdos técnicos o decisiones tomadas"],\n'
            '  "next_steps": ["Lista de próximos pasos prácticos"]\n'
            "}\n"
            "IMPORTANTE: Responde ÚNICAMENTE con el objeto JSON válido."
        )

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": True,
            "format": "json",
            "keep_alive": "10m",
            "options": {
                "temperature": 0.2,
                "num_ctx": 2048,
                "num_predict": 650
            }
        }

        resp = requests.post(f"{self.ollama_url}/api/generate", json=payload, stream=True, timeout=(5, 90))
        if resp.status_code == 200:
            chunks = []
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                    if obj.get("response"):
                        chunks.append(obj["response"])
                    if obj.get("done"):
                        break
                except Exception:
                    continue
            response_text = "".join(chunks).strip() or "{}"
            parsed = json.loads(response_text)
            return self._normalize_llm_report(parsed, self.ollama_model)
        return None

    # =========================================================================
    # FORMATEADORES PARA ARCHIVO .TXT, MARKDOWN (.MD) Y POPUP VISUAL
    # =========================================================================
    def format_for_markdown(self, report: Dict[str, Any]) -> str:
        """Genera la minuta ejecutiva en formato GitHub Flavored Markdown con tareas interactivas."""
        lines = [
            "\n\n---\n",
            "# 📋 Minuta Ejecutiva y Compromisos (Agente Local)",
            f"> **Motor de análisis:** `{report.get('source', 'Heurístico 100% Offline')}`\n",
            "## 📌 1. Resumen General de la Reunión",
            f"{report.get('summary', 'Sin resumen disponible.')}\n",
            "## ✅ 2. Compromisos Adquiridos y Responsabilidades (Action Items)"
        ]

        commits = report.get("commitments", [])
        if commits:
            for c in commits:
                assignee = c.get("assignee", "Participante")
                task = c.get("task", "")
                t_str = f" `[{c.get('time')}]`" if c.get("time") else ""
                lines.append(f"- [ ] **{assignee}**{t_str}: {task}")
        else:
            lines.append("- [x] *No se detectaron compromisos explícitos asumidos durante la sesión.*")
        lines.append("")

        lines.append("## 🔍 3. Temas Clave para Estudiar / Revisar / Investigar")
        topics = report.get("study_topics", [])
        if topics:
            for s in topics:
                if isinstance(s, dict):
                    topic_text = s.get("topic", "")
                    spk = f" *(mencionado por {s.get('speaker')})*" if s.get("speaker") else ""
                    lines.append(f"- 🔎 **{topic_text}**{spk}")
                else:
                    lines.append(f"- 🔎 {s}")
        else:
            lines.append("- *No se identificaron temas específicos de investigación o estudio posterior.*")
        lines.append("")

        lines.append("## 🎯 4. Acuerdos y Decisiones Técnicas")
        decs = report.get("decisions", [])
        if decs:
            for d in decs:
                if isinstance(d, dict):
                    lines.append(f"- 🎯 {d.get('decision', '')}")
                else:
                    lines.append(f"- 🎯 {d}")
        else:
            lines.append("- *No se registraron decisiones o acuerdos explícitos.*")
        lines.append("")

        lines.append("## 🚀 5. Próximos Pasos (Roadmap)")
        steps = report.get("next_steps", [])
        if steps:
            for i, step in enumerate(steps, 1):
                lines.append(f"{i}. {step}")
        else:
            lines.append("1. Continuar con el seguimiento de tareas en la próxima sincronización.")
        lines.append("\n---\n")

        return "\n".join(lines)

    def format_for_txt(self, report: Dict[str, Any]) -> str:
        """Genera el texto estructurado en formato limpio para anexar al final del archivo .txt."""
        sep = "=" * 76
        sub_sep = "-" * 76

        lines = [
            "\n",
            sep,
            "   📋 MINUTA EJECUTIVA Y COMPROMISOS DE LA REUNIÓN (AGENTE LOCAL)",
            f"   Motor de análisis: {report.get('source', 'Heurístico 100% Offline')}",
            sep,
            "",
            "📌 1. RESUMEN DE LA REUNIÓN:",
            f"   {report.get('summary', 'Sin resumen disponible.')}",
            ""
        ]

        # Compromisos adquiridos
        lines.append("✅ 2. COMPROMISOS ADQUIRIDOS Y RESPONSABILIDADES (ACTION ITEMS):")
        commits = report.get("commitments", [])
        if commits:
            for c in commits:
                assignee = c.get("assignee", "Participante")
                task = c.get("task", "")
                t_str = f" [{c.get('time')}]" if c.get("time") else ""
                lines.append(f"   • [{assignee}]{t_str}: {task}")
        else:
            lines.append("   • No se detectaron compromisos explícitos asumidos.")
        lines.append("")

        # Temas a estudiar / revisar
        lines.append("🔍 3. TEMAS CLAVE PARA ESTUDIAR / REVISAR / INVESTIGAR:")
        topics = report.get("study_topics", [])
        if topics:
            for s in topics:
                if isinstance(s, dict):
                    topic_text = s.get("topic", "")
                    spk = f" (mencionado por {s.get('speaker')})" if s.get("speaker") else ""
                    lines.append(f"   • {topic_text}{spk}")
                else:
                    lines.append(f"   • {s}")
        else:
            lines.append("   • No se identificaron temas específicos de estudio o revisión.")
        lines.append("")

        # Decisiones tomadas
        lines.append("🎯 4. ACUERDOS Y DECISIONES TÉCNICAS:")
        decs = report.get("decisions", [])
        if decs:
            for d in decs:
                if isinstance(d, dict):
                    lines.append(f"   • {d.get('decision', '')}")
                else:
                    lines.append(f"   • {d}")
        else:
            lines.append("   • No se registraron acuerdos explícitos.")
        lines.append("")

        # Próximos pasos
        lines.append("🚀 5. PRÓXIMOS PASOS (ROADMAP INMEDIATO):")
        steps = report.get("next_steps", [])
        if steps:
            for step in steps:
                lines.append(f"   1. {step}")
        else:
            lines.append("   • Continuar con el seguimiento en la próxima sincronización.")
        lines.append("")
        lines.append(sep + "\n")

        return "\n".join(lines)
