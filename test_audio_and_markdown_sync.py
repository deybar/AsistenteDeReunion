"""
Suite de Validación Integral: Grabación de Audio WAV Sincronizada, Generador Dual (.md + .json)
y Modo HUD Zen para el Asistente de Reunión Local.
"""

import os
import sys
import json
import wave
import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from audio_recorder import AudioMeetingRecorder
from transcript_manager import TranscriptManager
from meeting_agent import MeetingInsightsAgent

def run_tests():
    print("=" * 65)
    print("  TEST PIPELINE SINCRONIZADO: AUDIO WAV + MARKDOWN + TIMELINE JSON")
    print("=" * 65)

    test_dir = os.path.join(APP_DIR, "test_reuniones_sync")
    os.makedirs(test_dir, exist_ok=True)

    # -------------------------------------------------------------
    # TEST 1: Grabador de Audio en Streaming (.wav)
    # -------------------------------------------------------------
    print("\n[TEST 1] Verificación de AudioMeetingRecorder (WAV Streaming):")
    recorder = AudioMeetingRecorder(sample_rate=16000, channels=1)
    wav_path = os.path.join(test_dir, "test_session.wav")

    assert recorder.start_recording(wav_path) == True
    assert recorder.is_recording == True

    # Simular 3 segundos de audio en bloques de 100 ms (1600 muestras cada uno)
    sample_rate = 16000
    chunk_samples = 1600
    for _ in range(30):
        # Generar tono sintético
        t = np.linspace(0, 0.1, chunk_samples, endpoint=False)
        simulated_chunk = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        recorder.write_chunk(simulated_chunk)

    curr_time = recorder.get_current_audio_time_sec()
    print(f"  Tiempo de audio grabado reportado: {curr_time:.2f} s")
    assert 2.9 <= curr_time <= 3.1, f"Tiempo esperado ~3.0s, obtenido {curr_time}"

    meta = recorder.stop_recording()
    print(f"  Metadatos WAV generados: {meta}")
    assert os.path.exists(wav_path), "El archivo WAV no fue creado en disco"
    assert meta["duration_seconds"] >= 2.9

    # Validar cabeceras reales del archivo WAV generado
    with wave.open(wav_path, "rb") as wf:
        assert wf.getnchannels() == 1, "Debe ser canal mono"
        assert wf.getsampwidth() == 2, "Debe ser PCM 16-bit"
        assert wf.getframerate() == 16000, "Debe ser 16000 Hz"
        n_frames = wf.getnframes()
        dur = n_frames / 16000.0
        print(f"  Verificación interna WAV: {n_frames} frames, {dur:.2f} s")
        assert 2.9 <= dur <= 3.1
    print("=> TEST 1 superado exitosamente.")

    # -------------------------------------------------------------
    # TEST 2: Gestor de Transcripción Dual (.md + .json + .txt)
    # -------------------------------------------------------------
    print("\n[TEST 2] Verificación de TranscriptManager con Sincronización Temporal:")
    manager = TranscriptManager(base_dir=test_dir)
    print(f"  Sesión ID creada: {manager.session_id}")
    print(f"  Archivo MD:   {os.path.basename(manager.get_current_filepath())}")
    print(f"  Archivo WAV:  {os.path.basename(manager.get_current_wav_path())}")
    print(f"  Archivo JSON: {os.path.basename(manager.get_current_json_path())}")

    # Simular intervenciones con timestamps relativos de audio exactos
    dialogues = [
        {"start": 1.2, "end": 4.5, "clock": "10:30:05", "speaker": "Participante 1", "source": "pc", "text": "Iniciamos la revisión del sistema de sincronización."},
        {"start": 5.1, "end": 9.8, "clock": "10:30:10", "speaker": "Tú", "source": "mic", "text": "Hola a todos. Yo me comprometo a implementar la grabación WAV y el timeline JSON para la interfaz web."},
        {"start": 10.5, "end": 14.2, "clock": "10:30:16", "speaker": "Participante 2", "source": "pc", "text": "Excelente, es importante estudiar el framework de audio interactivo para la reproducción sincronizada."},
        {"start": 15.0, "end": 18.2, "clock": "10:30:22", "speaker": "Tú", "source": "mic", "text": "Perfecto, acordamos usar Markdown con Frontmatter y JSON sincronizado como estándar."}
    ]

    for d in dialogues:
        manager.log_entry(
            timestamp_str=d["clock"],
            speaker=d["speaker"],
            text=d["text"],
            start_sec=d["start"],
            end_sec=d["end"],
            source_type=d["source"]
        )

    entries = manager.get_entries()
    assert len(entries) == 4, f"Se esperaban 4 entradas, obtenidas {len(entries)}"
    print(f"  Se registraron {len(entries)} segmentos sincronizados.")
    print(f"  Primer segmento: start={entries[0]['start']}s, end={entries[0]['end']}s, text='{entries[0]['text'][:30]}...'")

    # Finalizar sesión y generar minuta estructurada
    agent = MeetingInsightsAgent()
    audio_meta = {
        "duration_seconds": 25.5,
        "duration_formatted": "00:00:25"
    }
    filepath_md, report = manager.finalize_meeting(agent, audio_metadata=audio_meta)

    # Validar archivo Markdown (.md)
    assert os.path.exists(manager.current_md_path), "No se generó el archivo .md"
    with open(manager.current_md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    assert "---" in md_content, "El archivo .md debe contener Frontmatter YAML"
    assert "audio_file:" in md_content, "El Frontmatter debe enlazar el audio_file"
    assert "timeline_file:" in md_content, "El Frontmatter debe enlazar el timeline_file"
    assert "# 📋 Minuta Ejecutiva y Compromisos" in md_content, "Debe contener la minuta"
    assert "- [ ]" in md_content or "- [x]" in md_content, "Debe contener checkboxes de compromisos"
    print("  Archivo Markdown (.md) estructurado verificado correctamente.")

    # Validar archivo Timeline JSON (.json) para el futuro frontend
    assert os.path.exists(manager.current_json_path), "No se generó el archivo .json"
    with open(manager.current_json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    assert json_data["session_id"] == manager.session_id
    assert json_data["duration_seconds"] == 25.5
    assert len(json_data["segments"]) == 4
    assert json_data["segments"][1]["start"] == 5.1
    assert json_data["segments"][1]["end"] == 9.8
    assert json_data["segments"][1]["speaker"] == "Tú"
    assert "summary" in json_data
    print("  Archivo Timeline JSON (.json) estructurado para Frontend verificado correctamente.")
    print("=> TEST 2 superado exitosamente.")

    # -------------------------------------------------------------
    # TEST 3: Interfaz Gráfica y Widget de Onda Reactiva
    # -------------------------------------------------------------
    print("\n[TEST 3] Verificación de la Interfaz HUD Zen (PyQt6):")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from meeting_window import MeetingWindow, AudioWavePulseWidget

    win_config = {
        "theme": "dark_carbon",
        "opacity": 94,
        "font_size": 14,
        "show_text_view": False,
        "window_pos_x": 100,
        "window_pos_y": 100,
        "window_width": 640
    }
    win = MeetingWindow(win_config)
    win.show()

    # Modo Zen / Cápsula minimalista: altura compacta
    assert win.show_text_view == False
    assert win.height() == 52, f"En modo Zen la altura debe ser 52 px, obtenida {win.height()}"
    assert win.transcript_browser.isVisible() == False

    # Medidor reactivo de audio
    win.set_audio_level(0.85)
    assert win.audio_wave.level >= 0.85

    # Alternar a modo expandido con texto visible
    win._toggle_text_view()
    assert win.show_text_view == True
    assert win.transcript_browser.isVisible() == True
    assert win.height() >= 180
    print("  Alternancia entre Modo Zen (Cápsula 52 px) y Modo Expandido verificado correctamente.")

    # Simular recepción de entrada con timestamps
    win.append_transcript_entry("10:30:15", "Tú", "Probando visualizador HUD Zen", "mic", 2.0, 5.0)
    assert win.lbl_speaker_badge.text() == "🎙️ Tú"
    print("  Recepción de intervención en la cápsula verificada.")
    print("=> TEST 3 superado exitosamente.")

    # -------------------------------------------------------------
    # TEST 4: Segmentación Dual sin Ping-Pong y Mezcla WAV 1:1
    # -------------------------------------------------------------
    print("\n[TEST 4] Verificación de Canales Aislados (Sin Ping-Pong) y Mezclador WAV:")
    import queue
    import time
    import threading
    from meeting_transcriber import LiveMeetingTranscriber
    from audio_mixer_capture import AudioMixerCaptureManager

    # 4A. Verificar segmentación aislada en LiveMeetingTranscriber
    test_q = queue.Queue()
    transcriber = LiveMeetingTranscriber(audio_queue=test_q, latency_mode="ultra_fast")
    transcriber.is_running = True

    t_seg = threading.Thread(target=transcriber._process_audio_loop, daemon=True)
    t_seg.start()

    chunk_samples_100ms = 1600
    t_vec = np.linspace(0, 0.1, chunk_samples_100ms, endpoint=False)
    voice_chunk = (np.sin(2 * np.pi * 220 * t_vec) * 0.15).astype(np.float32)  # RMS ~ 0.106
    silent_chunk = np.zeros(chunk_samples_100ms, dtype=np.float32)

    # 25 pares alternados mic(voz) / pc(silencio) = 2.5s simultáneos
    for _ in range(25):
        test_q.put((voice_chunk, "mic"))
        test_q.put((silent_chunk, "pc"))

    # 5 pares de silencio en ambos canales para disparar pausa
    for _ in range(5):
        test_q.put((silent_chunk, "mic"))
        test_q.put((silent_chunk, "pc"))

    time.sleep(0.35)
    transcriber.is_running = False
    t_seg.join(timeout=1.0)

    q_items = []
    while not transcriber._transcribe_queue.empty():
        q_items.append(transcriber._transcribe_queue.get_nowait())

    print(f"  Segmentos consolidados generados en modo mixto: {len(q_items)}")
    assert len(q_items) == 1, f"Se esperaba 1 segmento consolidado, obtenidos {len(q_items)}"
    seg_audio, seg_src, _, seg_start, seg_end = q_items[0]
    print(f"  Canal: {seg_src} | Muestras: {len(seg_audio)} ({len(seg_audio)/16000:.2f}s) | Rango: {seg_start:.2f}s -> {seg_end:.2f}s")
    assert seg_src == "mic", f"Canal esperado 'mic', obtenido {seg_src}"
    assert len(seg_audio) >= 16000 * 2.0, f"Segmento fragmentado: solo {len(seg_audio)} muestras"

    # 4B. Verificar duración WAV 1:1 en AudioMixerCaptureManager modo mixed
    wav_mix_path = os.path.join(test_dir, "test_mixed_1to1.wav")
    mix_rec = AudioMeetingRecorder(sample_rate=16000, channels=1)
    assert mix_rec.start_recording(wav_mix_path)
    mixer = AudioMixerCaptureManager(audio_queue=queue.Queue(), sample_rate=16000, recorder=mix_rec)
    mixer.current_mode = "mixed"
    mixer.is_paused = False

    # Simular 20 bloques de 100ms de cada canal (2.0s reales)
    for _ in range(20):
        with mixer._mix_lock:
            mixer._pending_pc_chunks.append(silent_chunk)
            mixer._pending_mic_chunks.append(voice_chunk)
        mixer._flush_mixed_recorder()

    mix_meta = mix_rec.stop_recording()
    print(f"  Duración WAV mixto grabado (2.0s reales): {mix_meta['duration_seconds']}s")
    assert 1.9 <= mix_meta["duration_seconds"] <= 2.1, f"Deriva temporal WAV detectada: {mix_meta['duration_seconds']}s"
    print("=> TEST 4 superado exitosamente.")

    print("\n" + "=" * 65)
    print("  RESULTADO: TODOS LOS TESTS PASARON CON ÉXITO (100% OPERATIVO)")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
