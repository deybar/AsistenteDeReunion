# 📦 02. Protocolo Tri-Formato (.wav, .md, .json)

El Asistente de Reunión Local implementa un estándar de guardado simultáneo en tres formatos complementarios dentro de la carpeta `reuniones/`:
1. **Audio Maestro (`.wav`)**
2. **Minuta Humana Estructurada (`.md`)**
3. **Timeline para Máquinas / Frontends (`.json`)**
4. *(Opcional)* Texto plano (`.txt`) para compatibilidad retroactiva.

Todos los archivos comparten el mismo identificador de sesión temporal:
`reunion_YYYYMMDD_HHMMSS`

---

## 1. Archivo de Audio Maestro (`.wav`)
- **Especificación:** PCM 16-bit Mono a 16.000 Hz.
- **Tasa de datos:** ~32 KB/s (~1.9 MB por minuto de reunión).
- **Escritura:** Streaming continuo sin buffers en memoria RAM.
- **Utilidad:** Conserva la evidencia auditiva completa para auditoría, re-escucha o entrenamiento futuro de modelos locales.

---

## 2. Archivo Markdown Estructurado (`.md`)
Diseñado para lectura humana, exportación a herramientas como Obsidian, Notion o GitHub y revisión de minutas ejecutivas.

### Estructura del Archivo

```markdown
---
session_id: reunion_20261119_105432
audio_file: reunion_20261119_105432.wav
created_at: 2026-11-19T10:54:32
duration_seconds: 182.4
speakers:
  - Tú
  - Participante 1
---

# 🎙️ Minuta de Reunión: 2026-11-19 10:54:32

## 💬 Transcripción Sincronizada con Audio

- `[00:02 ➔ 00:07]` **[Tú]**: Damos inicio a la sesión de arquitectura para revisar la integración del lanzador.
- `[00:08 ➔ 00:15]` **[Participante 1]**: Perfecto, ya tenemos las pruebas unitarias completadas en local.

---

## 📋 Minuta Ejecutiva y Compromisos

### 🎯 Resumen Ejecutivo
Se revisó el pipeline de captura y la sincronización con el formato JSON...

### ✅ Compromisos Adquiridos (Action Items)
- [ ] **Tú**: Actualizar la bitácora del proyecto y el control de versiones.
- [ ] **Participante 1**: Probar el lanzador en Windows 11.

### 📌 Decisiones Técnicas Clave
| # | Decisión Adoptada | Impacto Técnico |
|---|---|---|
| 1 | Uso de 16kHz PCM directo | Cero latencia y sincronía frame a frame |
```

---

## 3. Archivo Timeline JSON (`.json`)
Diseñado específicamente como contrato de datos para el **futuro frontend interactivo** (web o desktop).

### Esquema JSON

```json
{
  "session_id": "reunion_20261119_105432",
  "created_at": "2026-11-19T10:54:32",
  "audio_file": "reunion_20261119_105432.wav",
  "total_duration_seconds": 182.4,
  "speakers": ["Tú", "Participante 1"],
  "segments": [
    {
      "index": 1,
      "clock_time": "10:54:34",
      "start_sec": 2.1,
      "end_sec": 7.3,
      "time_range": "[00:02 ➔ 00:07]",
      "speaker": "Tú",
      "source": "microphone",
      "text": "Damos inicio a la sesión de arquitectura para revisar la integración del lanzador."
    },
    {
      "index": 2,
      "clock_time": "10:54:40",
      "start_sec": 8.0,
      "end_sec": 15.2,
      "time_range": "[00:08 ➔ 00:15]",
      "speaker": "Participante 1",
      "source": "loopback",
      "text": "Perfecto, ya tenemos las pruebas unitarias completadas en local."
    }
  ]
}
```

### Capacidades Habilitadas para el Frontend:
1. **Waveform Interactivo:** Cargar el `.wav` con Wavesurfer.js o reproductor Qt y renderizar la onda completa.
2. **Click-to-Seek:** Hacer clic en cualquier fila de la transcripción y saltar inmediatamente a `segment.start_sec`.
3. **Búsqueda Inteligente:** Filtrar por interlocutor o buscar palabras clave resaltando el fragmento en la línea de tiempo.
