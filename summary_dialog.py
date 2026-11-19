"""
Ventana de Visualización de la Minuta Ejecutiva y Compromisos Detectados.
Permite revisar, copiar al portapapeles y abrir el archivo de la reunión.
"""

from typing import Dict, Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QPushButton, QFrame, QApplication
)
from PyQt6.QtGui import QFont, QColor
from theme_config import get_theme_data

class MeetingSummaryDialog(QDialog):
    def __init__(self, report: Dict[str, Any], filepath: str, theme_key: str = "dark_carbon", parent=None):
        super().__init__(parent)
        self.report = report
        self.filepath = filepath
        self.theme_data = get_theme_data(theme_key)

        self.setWindowTitle("Minuta Ejecutiva y Compromisos de la Reunión")
        self.resize(760, 560)
        self.setMinimumSize(600, 420)
        self._init_ui()

    def _init_ui(self):
        t = self.theme_data
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.get('card_bg', '#121214')};
                color: {t.get('text_main', '#f4f4f5')};
            }}
            QTextBrowser {{
                background-color: {t.get('btn_bg', '#18181b')};
                color: {t.get('text_main', '#f4f4f5')};
                border: 1px solid {t.get('border', '#27272a')};
                border-radius: 8px;
                padding: 14px;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QPushButton {{
                background-color: {t.get('btn_bg', '#18181b')};
                color: {t.get('text_main', '#f4f4f5')};
                border: 1px solid {t.get('btn_border', '#3f3f46')};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('btn_bg_hover', '#27272a')};
            }}
            QPushButton#btn_copy {{
                background-color: {t.get('btn_accent_bg', '#0284c7')};
                color: #ffffff;
                border: none;
            }}
            QPushButton#btn_copy:hover {{
                background-color: {t.get('btn_accent_hover', '#0369a1')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Encabezado
        title_label = QLabel("📋 Minuta Ejecutiva y Compromisos Adquiridos", self)
        title_label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {t.get('text_accent', '#38bdf8')};")
        layout.addWidget(title_label)

        sub_label = QLabel(f"Generado localmente y anexado al archivo: {self.filepath}", self)
        sub_label.setStyleSheet(f"color: {t.get('text_muted', '#a1a1aa')}; font-size: 11px;")
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)

        # Visor de texto enriquecido HTML
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(self._build_html())
        layout.addWidget(self.browser)

        # Barra de botones inferior
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.btn_copy = QPushButton("📋 Copiar al Portapapeles", self)
        self.btn_copy.setObjectName("btn_copy")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        bottom_layout.addWidget(self.btn_copy)

        self.btn_open = QPushButton("📄 Abrir Archivo .txt", self)
        self.btn_open.clicked.connect(self._open_file)
        bottom_layout.addWidget(self.btn_open)

        bottom_layout.addStretch()

        self.btn_close = QPushButton("Cerrar", self)
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        layout.addLayout(bottom_layout)

    def _build_html(self) -> str:
        t = self.theme_data
        accent = t.get("text_accent", "#38bdf8")
        action_col = t.get("action_item_color", "#fbbf24")
        self_col = t.get("speaker_self", "#10b981")
        muted = t.get("text_muted", "#a1a1aa")
        text_col = t.get("text_main", "#f4f4f5")

        html = f"""
        <div style="font-size: 14px; line-height: 1.6; color: {text_col};">
            <h3 style="color: {accent}; margin-bottom: 6px;">📌 1. Resumen de la Reunión</h3>
            <p style="margin-top: 0; margin-bottom: 16px;">{self.report.get('summary', 'Sin resumen.')}</p>

            <h3 style="color: {action_col}; margin-bottom: 6px;">✅ 2. Compromisos Adquiridos (Action Items)</h3>
        """

        commits = self.report.get("commitments", [])
        if commits:
            html += "<ul>"
            for c in commits:
                assignee = c.get("assignee", "Participante")
                task = c.get("task", "")
                t_str = f" <span style='color: {muted}; font-size: 11px;'>[{c.get('time')}]</span>" if c.get("time") else ""
                badge_col = self_col if "Tú" in assignee else accent
                html += f"<li><b style='color: {badge_col};'>[{assignee}]</b>{t_str}: {task}</li>"
            html += "</ul>"
        else:
            html += f"<p style='color: {muted};'>No se detectaron compromisos explícitos.</p>"

        html += f"""
            <h3 style="color: {accent}; margin-bottom: 6px; margin-top: 16px;">🔍 3. Temas Clave para Estudiar / Revisar</h3>
        """
        topics = self.report.get("study_topics", [])
        if topics:
            html += "<ul>"
            for s in topics:
                if isinstance(s, dict):
                    topic_text = s.get("topic", "")
                    spk = f" <span style='color: {muted}; font-size: 11px;'>(por {s.get('speaker')})</span>" if s.get("speaker") else ""
                    html += f"<li><b>{topic_text}</b>{spk}</li>"
                else:
                    html += f"<li><b>{s}</b></li>"
            html += "</ul>"
        else:
            html += f"<p style='color: {muted};'>No se identificaron temas específicos de estudio.</p>"

        # Acuerdos y Decisiones
        decs = self.report.get("decisions", [])
        if decs:
            html += f"""
                <h3 style="color: {self_col}; margin-bottom: 6px; margin-top: 16px;">🎯 4. Decisiones y Acuerdos</h3>
                <ul>
            """
            for d in decs:
                dec_text = d.get("decision", "") if isinstance(d, dict) else str(d)
                html += f"<li>{dec_text}</li>"
            html += "</ul>"

        # Próximos pasos
        steps = self.report.get("next_steps", [])
        if steps:
            html += f"""
                <h3 style="color: {accent}; margin-bottom: 6px; margin-top: 16px;">🚀 5. Próximos Pasos</h3>
                <ol>
            """
            for step in steps:
                html += f"<li>{step}</li>"
            html += "</ol>"

        html += "</div>"
        return html

    def _copy_to_clipboard(self):
        text_plain = self.browser.toPlainText()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text_plain)
            self.btn_copy.setText("✓ ¡Copiado!")
            self.btn_copy.setStyleSheet("background-color: #10b981; color: white;")

    def _open_file(self):
        import os
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(self.filepath)
            except Exception:
                pass
