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

import re
import json
from typing import List, Dict, Any, Optional
import requests

class MeetingInsightsAgent:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen2.5:1.5b",
        ollama_enabled: bool = True
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.ollama_enabled = ollama_enabled

    def is_ollama_available(self) -> bool:
        """Verifica si el servicio local de Ollama está activo en el puerto 11434."""
        if not self.ollama_enabled:
            return False
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=1.2)
            return resp.status_code == 200
        except Exception:
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

        for item in entries:
            time_str = item.get("time", "")
            speaker = item.get("speaker", "Interlocutor")
            text = item.get("text", "").strip()
            if not text:
                continue

            speakers_participating.add(speaker)
            total_words += len(text.split())

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

        # Resumen general de la conversación
        spk_list = ", ".join(sorted(speakers_participating)) if speakers_participating else "Participantes"
        summary_intro = (
            f"Sesión con {len(speakers_participating)} interlocutor(es) activo(s) ({spk_list}) "
            f"con un total de {len(entries)} intervenciones registradas ({total_words} palabras)."
        )

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
    def _generate_with_ollama(self, entries: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        # Construir transcripción en texto plano
        lines = []
        for e in entries:
            lines.append(f"[{e.get('time', '')}] {e.get('speaker', '')}: {e.get('text', '')}")
        transcript_text = "\n".join(lines)

        prompt = (
            "Eres un Asistente Senior de Desarrollo de Software y Minutas de Reunión. "
            "A continuación tienes la transcripción fiel de una reunión de trabajo técnica.\n\n"
            f"--- TRANSCRIPCIÓN ---\n{transcript_text}\n--- FIN TRANSCRIPCIÓN ---\n\n"
            "Analiza detalladamente el texto y genera un JSON estrictamente estructurado con las siguientes claves:\n"
            "{\n"
            '  "summary": "Resumen conciso de los temas tratados y el objetivo de la reunión",\n'
            '  "commitments": [{"assignee": "Quién asumió el compromiso", "task": "Acción o entregable comprometido"}],\n'
            '  "study_topics": [{"topic": "Tema técnico, librería o arquitectura que se debe estudiar o revisar"}],\n'
            '  "decisions": ["Acuerdos técnicos o decisiones tomadas"],\n'
            '  "next_steps": ["Próximos pasos a seguir por el equipo"]\n'
            "}\n"
            "IMPORTANTE: Responde ÚNICAMENTE con el bloque JSON, sin introducciones ni saludos."
        )

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        resp = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            response_text = data.get("response", "{}")
            parsed = json.loads(response_text)
            parsed["source"] = f"ollama ({self.ollama_model})"
            return parsed
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
