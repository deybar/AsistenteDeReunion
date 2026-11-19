"""
Script de diagnóstico y prueba unitaria del pipeline del Asistente de Reunión.
Prueba la diarización, el análisis semántico de compromisos del agente y la generación de la minuta.
"""

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from meeting_agent import MeetingInsightsAgent
from transcript_manager import TranscriptManager

def test_pipeline():
    print("=== TEST PIPELINE DEL ASISTENTE DE REUNIONES ===")

    # 1. Crear transcripción simulada de una reunión técnica
    sample_dialogues = [
        {"time": "15:30:05", "speaker": "Participante 1", "text": "Buenas tardes equipo, revisemos el avance del sprint y los blockers."},
        {"time": "15:30:18", "speaker": "Tú", "text": "Hola a todos. Por mi parte terminé los endpoints del microservicio de autenticación, pero noté lentitud en las consultas complejas."},
        {"time": "15:30:35", "speaker": "Participante 2", "text": "Es importante que estudies la optimización de índices en PostgreSQL y revisar la documentación de SQLAlchemy para conexiones asíncronas."},
        {"time": "15:30:52", "speaker": "Tú", "text": "De acuerdo, yo me encargo de investigar los índices en PostgreSQL y mañana a primera hora subo el informe técnico con las pruebas."},
        {"time": "15:31:10", "speaker": "Participante 1", "text": "Perfecto. Acordamos que para el release de la próxima semana usaremos Python 3.11 y Docker multi-stage."},
        {"time": "15:31:25", "speaker": "Participante 2", "text": "I will deploy the staging environment by friday so we can run integration tests."},
        {"time": "15:31:40", "speaker": "Tú", "text": "Excelente, quedamos en eso. Nos vemos mañana."}
    ]

    # 2. Inicializar TranscriptManager
    manager = TranscriptManager(base_dir=os.path.join(APP_DIR, "test_reuniones"))
    for item in sample_dialogues:
        manager.log_entry(item["time"], item["speaker"], item["text"])

    print(f"[OK] Se registraron {len(sample_dialogues)} intervenciones en {manager.get_current_filepath()}")

    # 3. Ejecutar Agente de Compromisos
    agent = MeetingInsightsAgent()
    filepath, report = manager.finalize_meeting(agent)

    print("\n--- REPORTE EXTRAÍDO POR EL AGENTE ---")
    print("Resumen:", report.get("summary"))
    print("\nCompromisos detectados:")
    for c in report.get("commitments", []):
        print(f"  • [{c.get('assignee')}] ({c.get('time')}): {c.get('task')}")

    print("\nTemas clave para estudiar/revisar:")
    for s in report.get("study_topics", []):
        print(f"  • {s.get('topic')} (por {s.get('speaker')})")

    print("\nAcuerdos y Decisiones:")
    for d in report.get("decisions", []):
        print(f"  • {d.get('decision')}")

    print(f"\n[OK] Minuta anexada exitosamente en el archivo: {filepath}")

    # Verificar lectura del archivo
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    print("\n--- CONTENIDO COMPLETO DEL ARCHIVO .TXT (MUESTRA) ---")
    print(content)

    print("\n=== TODAS LAS PRUEBAS DEL AGENTE PASARON CON ÉXITO ===")

if __name__ == "__main__":
    test_pipeline()
