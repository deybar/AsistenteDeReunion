# 🎙️ Asistente de Reunión Local (100% Offline y Privado) 🔒

> **Versión 1.1.0** — Asistente inteligente de reuniones de escritorio para Windows con **Modo HUD Zen minimalista**, **grabación de audio raw (.wav) sincronizada**, **transcripción dual en Markdown (.md) y Timeline JSON (.json)**, y **Agente Inteligente Local** de minutas y compromisos. Captura el audio del PC (Teams, Google Meet, Zoom) y tu micrófono simultáneamente, identifica a los diferentes interlocutores (diarización acústica), transcribe fielmente con marcas de tiempo exactas relativas al audio `[MM:SS ➔ MM:SS]` y hora de reloj `[HH:MM:SS]`. Diseñado para máxima eficiencia de CPU, cero saturación visual y preparado para conectarse con futuros visores interactivos. **100% Confidencial y ejecutado en tu propio ordenador.**

---

## 📌 ¿De qué se trata el proyecto y cuál es su propósito?

En reuniones de trabajo internas (**Microsoft Teams, Google Meet, Zoom**), retrospectivas de sprint, daily meetings o llamadas técnicas de arquitectura, se comparte constantemente información corporativa altamente confidencial, credenciales, código fuente o planes estratégicos que **no pueden ni deben enviarse a servicios en la nube de terceros** (como Google Cloud Speech, Otter.ai o APIs externas) por motivos estrictos de privacidad y cumplimiento legal.

Este proyecto toma la esencia ágil y minimalista de **`08_TraductorLocal`** y la potencia de captura y diarización de **`09_TraductorAudio`**, evolucionándola a un **Asistente de Reuniones Completo**:

1. **Cápsula Flotante HUD Zen (Minimalismo Extremo):**
   - La ventana inicia por defecto en una barra horizontal compacta de solo **52 px de altura** con bordes redondeados y estilo translúcido moderno.
   - **Onda de audio reactiva (5 barras):** Pulsa dinámicamente en tiempo real según el volumen de la voz en colores cian y esmeralda, confirmando visualmente que el asistente está escuchando sin necesidad de leer texto.
   - **Indicador dinámico de interlocutor:** Muestra quién está hablando en tiempo real (`🎙️ Tú` o `🔊 Colegas`) y cronómetro de sesión `⏱️ 00:00`.
   - **Transcript plegable a demanda:** Un botón `[📜 Texto ▾/▴]` permite abrir o cerrar el visor de transcripción completa cuando se desee leer el diálogo.
2. **Grabación Streaming de Audio Directo a Disco (`.wav`):**
   - Graba el audio de la reunión en streaming directo a disco en formato PCM 16 kHz mono (`reuniones/reunion_YYYYMMDD_HHMMSS.wav`).
   - Almacena por bloques de bytes sin acumular muestras en la memoria RAM (consumo de RAM = 0 MB independientemente de la duración de la reunión).
3. **Ecosistema Tri-Formato Sincronizado (`.wav` + `.md` + `.json` + `.txt`):**
   - **Markdown (`.md`)**: Documento estructurado con metadatos YAML frontmatter (ID, fecha, duración, participantes, ruta del audio), diálogos formateados con enlaces de tiempo `[MM:SS ➔ MM:SS]` y minuta ejecutiva con checklists interactivos (`- [ ]`) y tablas GFM.
   - **Timeline JSON (`.json`)**: Archivo para máquinas y futuros frontends web/desktop con array de segmentos `{start_sec, end_sec, time_range, speaker, text, audio_file}` preparado para reproductores con forma de onda interactiva (wavesurfer.js) y *click-to-seek*.
   - **Texto Plano (`.txt`)**: Versión limpia clásica para compatibilidad retroactiva.
4. **Captura Multifuente Dual Simultánea (PC + Micrófono):** Escucha al mismo tiempo lo que dicen tus compañeros a través de los auriculares/altavoces (WASAPI Loopback) y lo que tú hablas por tu micrófono.
5. **Identificación de Interlocutores (Speaker Diarization):**
   - Tu micrófono se asigna directamente a `[Tú]` (o tu nombre configurado).
   - El audio del PC se analiza acústicamente en CPU para diferenciar automáticamente a `[Participante 1]`, `[Participante 2]`, etc.
6. **Agente de Minuta, Compromisos y Temas Clave:**
   - Detecta compromisos adquiridos y tareas asignadas (*action items*) clasificadas por responsable.
   - Resalta temas técnicos a estudiar, investigar o revisar.
   - Anexa toda la minuta estructurada al `.md` y `.txt` y la despliega en una ventana emergente interactiva.

---

## ✨ Características Principales

- **🧘 Modo HUD Zen Minimalista:**
  - Cápsula compacta (52 px) siempre visible (*Always on Top*).
  - Ecualizador / onda reactiva de audio animada en vivo según volumen.
  - Cronómetro de reunión y badge dinámico de hablante activo.
  - Visor de texto colapsable para evitar distracciones visuales.
- **🎙️+🔊 Modo Dual de Audio:**
  - *Dual (PC + Micrófono) [Recomendado]*: Captura tanto a los demás como a ti mismo.
  - *Solo PC*: Ideal para webinars, grabaciones o vídeos de formación.
  - *Solo Micrófono*: Ideal para reuniones presenciales donde todos hablan alrededor de la laptop.
- **📼 Grabador Directo a WAV:** Guarda la pista de audio completa para auditoría o escucha posterior.
- **🔗 Sincronización Temporal Milimétrica:** Cada frase tiene marcas de tiempo exactas que corresponden a los segundos reales del archivo WAV.
- **👥 Diarización Inteligente en Tiempo Real:** Detección de huella vocal en CPU sin latencia (< 5 ms).
- **🧠 Agente de Minutas con Enfoque Híbrido:**
  - *Nivel 1 (Por defecto)*: Motor semántico heurístico en español e inglés. Instantáneo y 100% offline.
  - *Nivel 2 (Opcional)*: Conexión automática con **Ollama** (`http://localhost:11434`) con modelos como `qwen2.5:1.5b` o `llama3.2`.
- **🎨 5 Temas Visuales:**
  - *Oscuro Carbón (Cine)*
  - *Oscuro Gris (Grafito)*
  - *Oscuro Moca Cálido*
  - *Oscuro Noche (Midnight)*
  - *Claro Suave (Nord)*
- **🛡️ Single Instance Guard:** Si se ejecuta mientras ya está abierto, enfoca y restaura la ventana existente.
- **🤫 Inicio 100% Silencioso:** Lanzador `iniciar.vbs` que arranca el asistente en segundo plano.

---

## 🛠️ Herramientas y Tecnologías Utilizadas

| Componente | Tecnología | Descripción |
|---|---|---|
| **Lenguaje** | Python 3.11+ | Base del proyecto |
| **Interfaz de Usuario (GUI)** | PyQt6 (Qt 6) | Ventana flotante sin bordes, transparencias nativas, estilos CSS modernos |
| **Captura de Audio WASAPI** | `pyaudiowpatch` | Captura simultánea de audio Loopback del sistema y micrófono físico |
| **Reconocimiento de Voz (ASR)** | `faster-whisper` | Whisper multilingüe (`base` / `small`) con cuantización INT8 en CPU |
| **Diarización de Hablantes** | Algoritmo acústico local (FFT + F0 + Bandas) | Identificación espectral en CPU (< 5 ms) y asignación directa de canal mic |
| **Agente de Compromisos** | Motor Semántico NLP + Ollama (Opcional) | Extracción de compromisos, temas de estudio, decisiones y roadmap |
| **Procesamiento de Señal** | `numpy` & `scipy.signal` | Remuestreo polifásico en tiempo real a 16 kHz mono |
| **Persistencia y Registro** | Archivos `.txt` UTF-8 | Guardado cronológico en disco en la carpeta `reuniones/` |

---

## 🚀 Cómo Ejecutar el Programa

### Opción 1: Ejecución Rápida
Haz doble clic en los archivos de la raíz del proyecto:
- **`iniciar.vbs`** *(Recomendado)*: Abre el asistente de forma **100% silenciosa** en segundo plano (sin ventana negra de CMD).
- **`iniciar.bat`**: Lanzador por lotes estándar.
- **`debug_consola.bat`**: Abre el asistente mostrando una consola CMD con todos los registros y diagnósticos en vivo.

### Opción 2: Para Desarrolladores
```bash
# El entorno virtual optimizado ya se encuentra en C:\Users\%USERNAME%\.audio_translator_venv
C:\Users\%USERNAME%\.audio_translator_venv\Scripts\python.exe main.py
```

---

## 📂 Estructura del Código

```text
10_Asistente-de-reunion/
├── main.py                     # Orquestador principal, bandeja del sistema y Single Instance Guard
├── audio_mixer_capture.py       # Captura dual simultánea: WASAPI Loopback (PC) + Micrófono
├── meeting_transcriber.py       # Transcripción multilingüe Faster-Whisper (ES/EN) con VAD desacoplado
├── speaker_diarizer.py          # Identificador de interlocutores ([Tú] vs Participantes acústicos)
├── meeting_agent.py             # Agente de IA para extracción de compromisos, temas clave y minuta
├── transcript_manager.py        # Registro cronológico continuo en .txt y adición de minuta
├── meeting_window.py            # Ventana flotante PyQt6 traslúcida con controles y transcripción en vivo
├── summary_dialog.py            # Diálogo emergente interactivo con la minuta generada y botón de copiar
├── theme_config.py              # Paletas de los 5 temas visuales y persistencia de configuración
├── config.json                  # Archivo de configuración persistente
├── requirements.txt             # Dependencias del proyecto
├── test_meeting_pipeline.py     # Script de prueba y validación del agente y la minuta
├── iniciar.vbs                  # Lanzador 100% silencioso
├── iniciar.bat                  # Lanzador estándar
├── debug_consola.bat            # Lanzador con consola activa para diagnóstico
├── .gitignore                   # Exclusiones de Git
└── reuniones/                   # Directorio donde se guardan automáticamente las sesiones en .txt
```

---

## 📄 Formato del Archivo `.txt` Generado

Cada reunión genera un archivo en `reuniones/reunion_YYYYMMDD_HHMMSS.txt` con la siguiente estructura:

```text
============================================================================
   ASISTENTE DE REUNIÓN LOCAL - TRANSCRIPCIÓN Y NOTAS CONFIDENCIALES
   Inicio de sesión: 2026-11-18 15:30:00
   Modo: 100% Offline / Privado (Local en PC)
============================================================================

[15:30:05] [Participante 1]
Buenas tardes equipo, revisemos el avance del sprint y los blockers.

[15:30:18] [Tú]
Hola a todos. Por mi parte terminé los endpoints del microservicio de autenticación, pero noté lentitud en las consultas complejas.

[15:30:35] [Participante 2]
Es importante que estudies la optimización de índices en PostgreSQL y revisar la documentación de SQLAlchemy para conexiones asíncronas.

[15:30:52] [Tú]
De acuerdo, yo me encargo de investigar los índices en PostgreSQL y mañana a primera hora subo el informe técnico con las pruebas.

[15:31:10] [Participante 1]
Perfecto. Acordamos que para el release de la próxima semana usaremos Python 3.11 y Docker multi-stage.

[15:31:25] [Participante 2]
I will deploy the staging environment by friday so we can run integration tests.

============================================================================
   📋 MINUTA EJECUTIVA Y COMPROMISOS DE LA REUNIÓN (AGENTE LOCAL)
   Motor de análisis: Heurístico 100% Offline
============================================================================

📌 1. RESUMEN DE LA REUNIÓN:
   Sesión con 3 interlocutor(es) activo(s) (Participante 1, Participante 2, Tú) con un total de 6 intervenciones registradas.

✅ 2. COMPROMISOS ADQUIRIDOS Y RESPONSABILIDADES (ACTION ITEMS):
   • [Tú] [15:30:52]: Investigar los índices en PostgreSQL y mañana a primera hora subo el informe técnico con las pruebas
   • [Participante 2] [15:31:25]: Deploy the staging environment by friday so we can run integration tests

🔍 3. TEMAS CLAVE PARA ESTUDIAR / REVISAR / INVESTIGAR:
   • Estudies la optimización de índices en PostgreSQL y revisar la documentación de SQLAlchemy para conexiones asíncronas (mencionado por Participante 2)

🎯 4. ACUERDOS Y DECISIONES TÉCNICAS:
   • Para el release de la próxima semana usaremos Python 3.11 y Docker multi-stage

🚀 5. PRÓXIMOS PASOS (ROADMAP INMEDIATO):
   1. Tú: Investigar los índices en PostgreSQL y mañana a primera hora subo el informe técnico con las pruebas
   2. Participante 2: Deploy the staging environment by friday so we can run integration tests
============================================================================
```

---

## 🔒 Privacidad y Seguridad

- **Cero telemetría y Cero conexión a internet:** Toda la captura de audio, transcripción, diarización y análisis de compromisos se realiza **100% en la memoria RAM y CPU de tu ordenador**.
- Tus reuniones internas, datos de clientes, arquitectura de software y secretos comerciales se mantienen estrictamente protegidos en tu equipo local.
