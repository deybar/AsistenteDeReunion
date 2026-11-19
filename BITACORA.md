# 📋 Bitácora de Desarrollo y Hoja de Ruta (Roadmap)
## Proyecto: Asistente de Reunión Local (100% Offline y Privado)

Esta bitácora documenta el diagnóstico de arquitectura, deudas técnicas resueltas y pendientes, el roadmap de evolución y el registro histórico de versiones del Asistente de Reunión.

---

## 🧭 1. Visión y Diagnóstico de Arquitectura (v1.1.0)

El proyecto es un asistente de reuniones de escritorio para Windows diseñado para operar de forma 100% local, privada y confidencial. Captura simultáneamente el audio del sistema (reuniones remotas en Teams, Meet, Zoom) y el micrófono local, identifica interlocutores por diarización acústica en CPU, transcribe mediante Whisper cuantizado (INT8), graba el audio en streaming continuo a `.wav` sin impacto en RAM y genera actas estructuradas en Markdown (`.md`) y JSON sincronizado (`.json`).

### Fortalezas Clave
- **Captura Dual Simultánea (WASAPI Loopback + Micrófono):** No requiere cables virtuales ni software de terceros; captura directamente altavoces y micrófono.
- **Cero Fuga a la Nube (100% Privado):** Todo el cómputo de voz a texto y generación de minutas corre localmente en el equipo.
- **Modo HUD Zen Minimalista:** Cápsula flotante ultra-compacta (52 px) con onda reactiva de 5 barras que pulsa al ritmo del volumen de voz, eliminando distracciones visuales.
- **Sincronización Milimétrica Audio-Texto:** El conteo exacto de muestras del grabador WAV permite enlazar cada segmento de transcripción con los segundos reales del archivo de audio.
- **Ecosistema Tri-Formato Preparado para Frontend:** Genera `.wav` (audio raw), `.md` (minuta estructurada con Frontmatter YAML y tareas interactivas) y `.json` (timeline para reproductores con click-to-seek interactivo).

---

## 🔍 2. Deudas Técnicas y Oportunidades de Mejora

| ID | Área | Descripción de la Oportunidad / Deuda | Estado / Prioridad |
|---|---|---|---|
| **DT-AR01** | **Rendimiento** | Scroll continuo de transcripción saturaba la GPU/CPU y distraía en reuniones. | **RESUELTO (v1.1.0 HUD Zen)** |
| **DT-AR02** | **Almacenamiento** | Solo se guardaba texto plano `.txt`; no había archivo de audio ni marcas de tiempo relativas. | **RESUELTO (v1.1.0 WAV + MD + JSON)** |
| **DT-AR03** | **Robustez Arranque** | Fallo por import de typing `Any` en `audio_mixer_capture.py`. | **RESUELTO (v1.1.0)** |
| **DT-AR04** | **Diarización Dinámica** | La diarización actual diferencia entre Tú (mic) y Colegas (loopback con clustering acústico). Podría enriquecerse con perfiles de voz precargados de compañeros recurrentes. | **Media** |
| **DT-AR05** | **Compresión Opcional** | Los archivos `.wav` son PCM 16kHz (~1.9 MB/minuto). Evaluar compresión local a `.opus` o `.flac` al finalizar la reunión si el usuario desea ahorrar espacio. | **Media** |
| **DT-AR06** | **Atajos Globales (Mute)** | Botón de silencio rápido o atajo global de teclado para pausar temporalmente la captura/grabación. | **Alta** |

---

## 🗺️ 3. Plan de Trabajo y Fases de Evolución

```mermaid
flowchart LR
    Fase1["Fase 1: HUD Zen y Tri-Formato (Completada)"] --> Fase2["Fase 2: Perfiles Vocales y Atajos"]
    Fase2 --> Fase3["Fase 3: Visor / Frontend de Reuniones"]
    Fase3 --> Fase4["Fase 4: Integración Suite IA"]
```

### 🔹 Fase 1: HUD Zen, Grabación WAV y Tri-Formato Sincronizado (Completada - v1.1.0)
- [x] Rediseño de interfaz a cápsula minimalista HUD Zen (52 px de altura).
- [x] Widget de onda reactiva animada en tiempo real según el volumen RMS capturado.
- [x] Ocultación del scroll continuo de texto, accesible bajo demanda con `[📜 Texto ▾/▴]`.
- [x] Módulo `AudioMeetingRecorder` para streaming directo a `.wav` (16 kHz mono) con 0 RAM retenida.
- [x] Módulo `TranscriptManager` para generación sincronizada tri-formato (`.wav`, `.md`, `.json`, `.txt`).
- [x] Inclusión de Frontmatter YAML, tablas de decisiones y checklists interactivos (`- [ ]`) en el `.md`.
- [x] Generación de timeline `.json` estructurado para click-to-seek en frontend interactivo.
- [x] Suite de pruebas automatizadas y repositorio Git inicializado.

### 🔹 Fase 2: Atajos Globales y Enriquecimiento de Diarización
- [ ] Atajo global de teclado (ej. `Ctrl+Shift+M`) para Pausar / Reanudar la captura de audio en cualquier momento.
- [ ] Soporte para bautizar a los participantes durante o al final de la reunión (ej: renombrar `Participante 1` a `Carlos`).
- [ ] Selector de micrófono / dispositivo de salida directo desde el menú de opciones sin editar `config.json`.

### 🔹 Fase 3: Visor / Intérprete Interactivo de Grabaciones
- [ ] Desarrollo de una aplicación frontend (web local o desktop) compartida por la suite:
  - Explorador de sesiones de reuniones anteriores.
  - Reproductor con visualizador de ondas (Wavesurfer.js) sincronizado con el `.json`.
  - Clic en cualquier párrafo de la transcripción para reproducir el audio en ese segundo exacto.
  - Gestión interactiva de compromisos pendientes (marcar tareas como completadas).
  - Exportación de minutas a PDF / Word / Correo electrónico corporativo.

### 🔹 Fase 4: Ecosistema Unificado de Productividad
- [ ] Replicar el formato tri-formato en `09_TraductorAudio` (subtítulos y traducciones sincronizadas con audio).
- [ ] Integración profunda con el lanzador `12_Lanzador-Apps-IA` para monitorizar estado, duración y grabaciones recientes desde el panel flotante.

---

## 📝 4. Registro Histórico de Cambios (Changelog)

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/) y versionado semántico.

### [1.1.0] - 2026-11-19
#### Añadido
- **Modo HUD Zen Minimalista:** Ventana compacta estilo cápsula flotante (52 px de altura) con esquinas redondeadas y translucidez.
- **Onda Reactiva Animada (`AudioWavePulseWidget`):** 5 barras que modulan su altura y color dinámicamente según la intensidad de la voz (cian en reposo, esmeralda activo).
- **Grabación Streaming a `.wav`:** Grabador maestro `AudioMeetingRecorder` que vuelca el audio en bloques continuos a disco en 16 kHz mono PCM, garantizando 0 MB de consumo de RAM acumulativo.
- **Formato Dual Estructurado (`.md` + `.json`):**
  - **Markdown (`.md`)**: Frontmatter YAML con metadatos de sesión, marcas de tiempo relativas al audio `[MM:SS ➔ MM:SS]` y minuta con tablas GFM y tareas interactivas (`- [ ]`).
  - **Timeline JSON (`.json`)**: Array de segmentos temporales `{start_sec, end_sec, time_range, speaker, text}` preparado para integración con reproductores web interactivos.
- **Transcriptor con Marcas Temporales Relativas:** `LiveMeetingTranscriber` calcula el offset en segundos desde el inicio de la grabación para cada intervención.
- **Suite de Pruebas Automatizadas:** Creación de `test_audio_and_markdown_sync.py` validando grabación WAV, dualidad MD/JSON y funcionalidad del HUD Zen.
- **Repositorio Git y Versionado:** Inicialización de Git en la rama `main` con `.gitignore` exhaustivo.

#### Corregido
- **Importación de Tipos en Captura:** Corrección de `NameError: name 'Any' is not defined` en `audio_mixer_capture.py` que impedía el arranque en modo silencioso.
- **Sobrecarga de Renderizado:** Eliminada la renderización continua de texto en primer plano, optimizando el uso de CPU/GPU.

### [1.0.0] - 2026-11-18
#### Añadido
- Versión inicial del Asistente de Reunión Local 100% Offline.
- Captura dual WASAPI Loopback (PC) y Micrófono.
- Diarización acústica básica en CPU para participantes remotos.
- Transcripción Whisper INT8 multilingüe (Español / Inglés).
- Agente heurístico y conector con Ollama para resumen de minutas y compromisos.
- Almacenamiento en archivos de texto plano `.txt`.
- Control de instancia única por sockets locales `QLocalServer`.
