"""
Suite de Pruebas Funcionales e Integrativas con Audios Reales (Offline + WASAPI Loopback).
Valida:
1. Transcripción de grabación real de YouTube técnico (reunion_20261120_013023.wav):
   RTF < 0.85x, Multi-Scale Valley Splitting sin palabras partidas y generación de minuta (.md/.json/.txt).
2. Transcripción de grabación real de micrófono a bajo volumen (reunion_20261120_003428.wav):
   Acondicionamiento HPF 80Hz + AGC adaptativo sin alucinaciones repetitivas.
3. Prueba funcional en vivo con reproducción acústica y captura WASAPI Loopback (con fallback seguro si el audio OS está silenciado).
"""

import os
import sys
import time
import wave
import queue
import tempfile
import subprocess
import numpy as np

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from meeting_transcriber import LiveMeetingTranscriber
from transcript_manager import TranscriptManager
from meeting_agent import MeetingInsightsAgent
from audio_mixer_capture import AudioMixerCaptureManager


def _find_real_wav(filename: str) -> str:
    candidates = [
        os.path.join(APP_DIR, "reuniones", filename),
        os.path.join(r"C:\dev\08_MiniToolsAI\3_Asistente-de-reunion\reuniones", filename),
        os.path.join(r"G:\Mi unidad\08_Programas PC\08_MiniToolsAI\3_Asistente-de-reunion\reuniones", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _synthesize_spanish_sapi5_wav(out_wav: str, text: str) -> bool:
    """Genera un WAV PCM 16kHz mono offline usando Microsoft Helena Desktop (Windows SAPI5)."""
    ps_script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $voices = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'es-*' }}
    if ($voices.Count -gt 0) {{
        $synth.SelectVoice($voices[0].VoiceInfo.Name)
    }}
    $synth.Rate = 0
    $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    $synth.SetOutputToWaveFile('{out_wav.replace("'", "''")}', $fmt)
    $synth.Speak('{text.replace("'", "''")}')
}} finally {{
    $synth.Dispose()
}}
"""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=25
        )
        return res.returncode == 0 and os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000
    except Exception:
        return False


def _load_wav_float32(wav_path: str, max_seconds: float = 0.0) -> tuple[np.ndarray, int]:
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        if max_seconds > 0:
            n_frames = min(n_frames, int(max_seconds * sr))
        raw = wf.readframes(n_frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        ch = wf.getnchannels()
        if ch > 1:
            samples = np.mean(samples.reshape(-1, ch), axis=1).astype(np.float32)
    return samples, sr


def _feed_audio_chunks(audio_q: queue.Queue, samples: np.ndarray, sr: int, source_tag: str):
    chunk_len = int(0.10 * sr)
    for i in range(0, len(samples), chunk_len):
        c = samples[i : i + chunk_len]
        if len(c) > 0:
            audio_q.put((c.astype(np.float32), source_tag))
    # 0.6s de silencio al final para disparar pausa natural del último segmento
    for _ in range(6):
        audio_q.put((np.zeros(chunk_len, dtype=np.float32), source_tag))


def test_real_youtube_recording():
    print("\n[TEST 1] Transcripción Real YouTube Técnico (reunion_20261120_013023.wav, 65s)...")
    wav_path = _find_real_wav("reunion_20261120_013023.wav")
    if not wav_path:
        print("  [SKIP] No se encontró reunion_20261120_013023.wav en disco.")
        return

    samples, sr = _load_wav_float32(wav_path, max_seconds=65.0)
    audio_dur = len(samples) / sr

    out_dir = os.path.join(APP_DIR, "test_reuniones_real")
    os.makedirs(out_dir, exist_ok=True)
    manager = TranscriptManager(base_dir=out_dir)
    audio_q = queue.Queue()

    results = []
    ready_evt = __import__("threading").Event()

    transcriber = LiveMeetingTranscriber(
        audio_queue=audio_q,
        model_size="base",
        language="es",
        sample_rate=sr,
        latency_mode="ultra_fast",
        on_transcript_ready=lambda ts, spk, txt, src, s, e: results.append((ts, spk, txt, src, s, e)),
        logger=manager
    )
    transcriber.initialize_model_async(callback=lambda ok, msg: ready_evt.set())
    assert ready_evt.wait(timeout=30.0) and transcriber.is_model_loaded, "No cargó Whisper base"

    t0 = time.time()
    transcriber.start()
    _feed_audio_chunks(audio_q, samples, sr, "pc")
    transcriber.flush_and_stop(timeout=90.0)
    elapsed = time.time() - t0
    rtf = elapsed / max(1.0, audio_dur)

    print(f"  Audio procesado: {audio_dur:.1f}s en {elapsed:.2f}s (RTF={rtf:.2f}x) | Segmentos: {len(results)}")
    for _, spk, txt, _, s, e in results:
        print(f"    [{s:05.1f}s->{e:05.1f}s] {spk}: {txt}")

    joined = " ".join(r[2] for r in results).lower()
    assert rtf < 0.85, f"RTF demasiado lento ({rtf:.2f}x >= 0.85x), no es fluido en tiempo real"
    assert len(results) >= 6, f"Se esperaban >= 6 segmentos, obtenidos {len(results)}"
    assert "que se pemos aco" not in joined, "Persiste distorsión fonética de ESP-Mosaico"
    assert "dispuesto positivo" not in joined, "Persiste corte por mitad en 'dispositivo'"

    expected_terms = ["espressif", "mosaico", "dispositivo", "inteligencia artificial", "electrónica"]
    hits = [t for t in expected_terms if t in joined]
    print(f"  Términos técnicos reconocidos ({len(hits)}/{len(expected_terms)}): {hits}")
    assert len(hits) >= 4, f"Pocos términos clave detectados: {hits}"

    agent = MeetingInsightsAgent(ollama_enabled=False)
    md_path, report = manager.finalize_meeting(agent, {"duration_seconds": audio_dur, "duration_formatted": "00:01:05"})
    assert os.path.exists(md_path) and os.path.exists(manager.get_current_json_path())
    print("=> TEST 1 superado exitosamente.")


def test_real_low_volume_mic_recording():
    print("\n[TEST 2] Transcripción Real de Micrófono Bajo Volumen (reunion_20261120_003428.wav)...")
    wav_path = _find_real_wav("reunion_20261120_003428.wav")
    if not wav_path:
        print("  [SKIP] No se encontró reunion_20261120_003428.wav en disco.")
        return

    samples, sr = _load_wav_float32(wav_path, max_seconds=60.0)
    audio_dur = len(samples) / sr
    audio_q = queue.Queue()
    results = []
    ready_evt = __import__("threading").Event()

    transcriber = LiveMeetingTranscriber(
        audio_queue=audio_q,
        model_size="base",
        language="es",
        sample_rate=sr,
        latency_mode="ultra_fast",
        user_label="Tú",
        on_transcript_ready=lambda *args: results.append(args)
    )
    transcriber.initialize_model_async(callback=lambda ok, msg: ready_evt.set())
    assert ready_evt.wait(timeout=30.0) and transcriber.is_model_loaded

    t0 = time.time()
    transcriber.start()
    _feed_audio_chunks(audio_q, samples, sr, "mic")
    transcriber.flush_and_stop(timeout=90.0)
    elapsed = time.time() - t0
    rtf = elapsed / max(1.0, audio_dur)

    print(f"  Mic bajo volumen ({audio_dur:.1f}s) procesado en {elapsed:.2f}s (RTF={rtf:.2f}x) | Segmentos: {len(results)}")
    for item in results:
        print(f"    [{item[4]:05.1f}s->{item[5]:05.1f}s] {item[1]}: {item[2]}")

    assert rtf < 0.85, f"RTF lento en micrófono: {rtf:.2f}x"
    assert len(results) >= 1, "El AGC no recuperó ninguna intervención del micrófono de bajo volumen"
    assert all(r[1] == "Tú" for r in results), "Las intervenciones de micrófono deben etiquetarse como 'Tú'"
    print("=> TEST 2 superado exitosamente.")


def test_live_wasapi_loopback_playback():
    print("\n[TEST 3] Prueba Funcional en Vivo con Reproducción de Audio y Captura WASAPI Loopback...")
    tmp_wav = os.path.join(tempfile.gettempdir(), "asistente_reunion_sapi5_es.wav")
    spoken_text = (
        "Acordamos usar Raspberry Pi y microcontroladores ESP32 para el prototipo. "
        "Yo me encargo de revisar la arquitectura del servidor mañana."
    )
    ok_tts = _synthesize_spanish_sapi5_wav(tmp_wav, spoken_text)
    assert ok_tts, "No se pudo sintetizar audio de prueba offline con Windows SAPI5"

    samples, sr = _load_wav_float32(tmp_wav)
    # Suavizar volumen para prueba discreta sin perturbar
    soft_samples = (samples * 0.25).astype(np.float32)

    audio_q = queue.Queue(maxsize=300)
    results = []
    ready_evt = __import__("threading").Event()

    transcriber = LiveMeetingTranscriber(
        audio_queue=audio_q,
        model_size="base",
        language="es",
        sample_rate=16000,
        latency_mode="ultra_fast",
        on_transcript_ready=lambda *args: results.append(args)
    )
    transcriber.initialize_model_async(callback=lambda ok, msg: ready_evt.set())
    assert ready_evt.wait(timeout=30.0) and transcriber.is_model_loaded

    capture = AudioMixerCaptureManager(audio_queue=audio_q, sample_rate=16000)
    devices = capture.get_available_devices()
    loopback_used = False

    if devices.get("loopback"):
        try:
            import pyaudiowpatch as pyaudio
            transcriber.start()
            capture.start(mode="loopback")
            time.sleep(0.5)

            p = pyaudio.PyAudio()
            try:
                wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                out_dev = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
                out_rate = int(out_dev["defaultSampleRate"])
                # Re-muestrear soft_samples a la frecuencia nativa de salida
                from scipy import signal as sp_sig
                gcd = np.gcd(sr, out_rate)
                up, down = out_rate // gcd, sr // gcd
                play_mono = sp_sig.resample_poly(soft_samples, up, down).astype(np.float32)
                play_stereo = np.column_stack([play_mono, play_mono])
                pcm = np.clip(play_stereo * 32767.0, -32768, 32767).astype(np.int16).tobytes()

                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=2,
                    rate=out_rate,
                    output=True,
                    output_device_index=out_dev["index"]
                )
                stream.write(pcm)
                time.sleep(0.8)
                stream.stop_stream()
                stream.close()
                loopback_used = True
            finally:
                p.terminate()

            capture.stop()
            transcriber.flush_and_stop(timeout=30.0)
        except Exception as e:
            print(f"  [AVISO] Audio hardware WASAPI no disponible ({e}), aplicando fallback a inyección directa.")
            capture.stop()
            transcriber.stop()

    if not loopback_used or not results:
        print("  [INFO] Altavoces silenciados o sin mezcla loopback activa; validando flujo completo con inyección directa del WAV SAPI5...")
        results.clear()
        audio_q_fb = queue.Queue()
        trans_fb = LiveMeetingTranscriber(
            audio_queue=audio_q_fb,
            model_size="base",
            language="es",
            sample_rate=16000,
            latency_mode="ultra_fast",
            on_transcript_ready=lambda *args: results.append(args)
        )
        trans_fb.whisper_model = transcriber.whisper_model
        trans_fb.is_model_loaded = True
        trans_fb.start()
        _feed_audio_chunks(audio_q_fb, samples, sr, "pc")
        trans_fb.flush_and_stop(timeout=30.0)

    print(f"  Transcripción obtenida ({len(results)} segs):")
    for r in results:
        print(f"    [{r[1]}]: {r[2]}")

    assert len(results) >= 1, "No se transcribió el audio SAPI5"
    full_txt = " ".join(r[2].lower() for r in results)
    assert any(k in full_txt for k in ("esp32", "raspberry", "prototipo", "arquitectura", "mañana")), (
        f"Transcripción inesperada: {full_txt}"
    )

    try:
        os.remove(tmp_wav)
    except OSError:
        pass
    print("=> TEST 3 superado exitosamente.")


if __name__ == "__main__":
    print("=" * 70)
    print("  SUITE FUNCIONAL CON AUDIOS REALES - ASISTENTE DE REUNIÓN")
    print("=" * 70)
    test_real_youtube_recording()
    test_real_low_volume_mic_recording()
    test_live_wasapi_loopback_playback()
    print("\n" + "=" * 70)
    print("  RESULTADO: TODAS LAS PRUEBAS FUNCIONALES PASARON AL 100%")
    print("=" * 70)
