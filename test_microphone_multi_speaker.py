"""
Prueba unitaria de diarización multilocutor en un mismo micrófono.
Simula dos voces distintas (diferente F0 y distribución espectral) ingresando por el mismo canal 'mic'.
"""

import numpy as np
from speaker_diarizer import MeetingSpeakerDiarizer

def generate_voice_tone(f0: float, duration_s: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    """Genera una señal que simula armónicos de voz humana con un tono fundamental f0."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    # Fundamental + armónicos con decaimiento natural
    signal = 0.5 * np.sin(2 * np.pi * f0 * t)
    signal += 0.3 * np.sin(2 * np.pi * (2 * f0) * t)
    signal += 0.15 * np.sin(2 * np.pi * (3 * f0) * t)
    signal += 0.08 * np.sin(2 * np.pi * (4 * f0) * t)
    # Añadir modulación de envolvente
    envelope = np.sin(np.pi * t / duration_s) ** 0.5
    return (signal * envelope).astype(np.float32)

def test_mic_diarization():
    print("=== TEST: DOS PERSONAS HABLANDO POR EL MISMO MICRÓFONO ===")
    diarizer = MeetingSpeakerDiarizer(user_label="Tú", multi_local_mode=True)

    # Persona A (Voz grave, F0 ~ 110 Hz)
    voice_a = generate_voice_tone(f0=110.0)

    # Persona B (Voz aguda o diferente timbre, F0 ~ 230 Hz)
    voice_b = generate_voice_tone(f0=230.0)

    # 1. Habla la Persona A por el micrófono
    spk1 = diarizer.identify_speaker(voice_a, source_type="mic")
    print(f"1. Intervención 1 (Persona A por Mic) -> Identificado como: [{spk1}]")
    assert spk1 == "Tú", f"Esperado 'Tú', obtenido '{spk1}'"

    # 2. Habla la Persona B por el MISMO micrófono
    spk2 = diarizer.identify_speaker(voice_b, source_type="mic")
    print(f"2. Intervención 2 (Persona B por Mic) -> Identificado como: [{spk2}]")
    assert spk2 == "Local 2", f"Esperado 'Local 2', obtenido '{spk2}'"

    # 3. Vuelve a hablar la Persona A por el micrófono
    spk3 = diarizer.identify_speaker(voice_a, source_type="mic")
    print(f"3. Intervención 3 (Vuelve a hablar Persona A por Mic) -> Identificado como: [{spk3}]")
    assert spk3 == "Tú", f"Esperado 'Tú', obtenido '{spk3}'"

    # 4. Vuelve a hablar la Persona B por el micrófono
    spk4 = diarizer.identify_speaker(voice_b, source_type="mic")
    print(f"4. Intervención 4 (Vuelve a hablar Persona B por Mic) -> Identificado como: [{spk4}]")
    assert spk4 == "Local 2", f"Esperado 'Local 2', obtenido '{spk4}'"

    # 5. Habla alguien por el PC (Loopback)
    voice_pc = generate_voice_tone(f0=160.0)
    spk_pc = diarizer.identify_speaker(voice_pc, source_type="pc")
    print(f"5. Intervención 5 (Alguien por el PC) -> Identificado como: [{spk_pc}]")
    assert spk_pc == "Participante 1", f"Esperado 'Participante 1', obtenido '{spk_pc}'"

    print("\n✓ ¡PRUEBA EXITOSA! El sistema diferenció correctamente a ambas personas compartiendo el mismo micrófono.")

if __name__ == "__main__":
    test_mic_diarization()
