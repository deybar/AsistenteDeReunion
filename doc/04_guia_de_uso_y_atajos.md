# 🚀 04. Guía de Uso y Configuración

Guía práctica para ejecutar, configurar y personalizar el Asistente de Reunión Local en Windows.

---

## 🏁 Formas de Iniciar el Asistente

### Opción 1: Desde el Lanzador Flotante (Recomendado)
Haz clic en el icono minimalista `⚡` del lanzador y selecciona la tarjeta **🎙️ Asistente de Reunión**.

### Opción 2: Inicio Silencioso Directo
Haz doble clic en `iniciar.vbs` en la raíz de la carpeta del proyecto. Se ejecutará en segundo plano con `pythonw.exe` sin abrir ventanas CMD.

### Opción 3: Modo Depuración / Consola
Haz doble clic en `debug_consola.bat` si deseas ver los logs de HuggingFace, VAD, PyAudio y Whisper en tiempo real en una consola.

---

## ⚙️ Menú de Opciones (`⚙`)

Al hacer clic en el engranaje `⚙` de la barra de herramientas, tienes acceso directo a:

- **📂 Abrir Carpeta de Reuniones:** Abre el explorador de Windows en la carpeta `reuniones/`.
- **📄 Abrir Última Minuta (.md):** Abre la minuta estructurada actual en tu editor predeterminado (Obsidian, VS Code, Bloc de Notas).
- **🎵 Reproducir Último Audio (.wav):** Abre la grabación de audio en tu reproductor multimedia.
- **🎙️ Fuente de Audio:**
  - *Dual (PC + Micrófono)*: Predeterminado para capturar a todos los participantes.
  - *Solo PC*: Para seminarios web o conferencias donde solo escuchas.
  - *Solo Micrófono*: Para reuniones presenciales de sala.
- **⚡ Modo de Latencia:**
  - *Ultra Rápido (1.5s)*: Ideal para seguimiento en vivo.
  - *Equilibrado (3.0s)*: Mayor precisión gramatical.
  - *Alta Precisión (5.0s)*: Ideal para contextos con vocabulario técnico complejo.
- **🌐 Idioma:** Detección automática, Español o Inglés.
- **🎨 Cambiar Tema:** Elige entre *Oscuro Carbón*, *Oscuro Gris*, *Moca Cálido*, *Noche Midnight* y *Claro Nord*.
- **➕ Nueva Reunión:** Cierra la sesión actual (sellando el `.wav`, `.md` y `.json`) e inicia una reunión limpia con nuevos archivos.

---

## 🤖 Integración Opcional con Ollama Local

El asistente incluye por defecto un motor semántico heurístico en español e inglés que funciona al 100% sin dependencias externas.

Si deseas resúmenes generativos con modelos de lenguaje locales (LLMs):
1. Instala [Ollama](https://ollama.ai) en Windows.
2. Descarga un modelo liviano en consola:
   ```cmd
   ollama pull qwen2.5:1.5b
   # O alternativamente:
   ollama pull llama3.2:1b
   ```
3. El asistente detectará Ollama automáticamente en `http://localhost:11434` al pulsar `[✨ Minuta]`.

---

## 🔧 Archivo de Configuración (`config.json`)

Los ajustes se persisten automáticamente en `config.json`:
```json
{
  "theme": "dark_carbon",
  "font_size": 13,
  "opacity": 0.95,
  "audio_source": "mixed",
  "language": "es",
  "model_size": "tiny",
  "latency_mode": "ultra_fast",
  "user_label": "Tú",
  "save_dir": "reuniones",
  "ollama_enabled": true,
  "ollama_url": "http://localhost:11434",
  "ollama_model": "qwen2.5:1.5b",
  "zen_mode": true
}
```
