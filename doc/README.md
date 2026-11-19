# 📚 Documentación Técnica del Asistente de Reunión Local

Bienvenido a la documentación oficial y técnica del **Asistente de Reunión Local (100% Offline y Privado)**. Este conjunto de documentos detalla la arquitectura interna del sistema, los formatos de datos y audio, las directrices de interfaz minimalista y las guías de uso.

---

## 🗂️ Índice de Contenidos

1. [**01. Arquitectura y Flujo de Procesamiento**](file:///G:/Mi%20unidad/08_Programas%20PC/10_Asistente-de-reunion/doc/01_arquitectura_y_flujo.md)
   - Explicación del pipeline de audio: captura dual WASAPI, mezcla, VAD, diarización en CPU, Whisper y agente de minutas.
2. [**02. Protocolo Tri-Formato (.wav, .md, .json)**](file:///G:/Mi%20unidad/08_Programas%20PC/10_Asistente-de-reunion/doc/02_protocolo_tri_formato.md)
   - Estructura de almacenamiento, Frontmatter YAML en Markdown, formato JSON para frontends interactivos con *click-to-seek* y grabación de audio PCM.
3. [**03. Modo HUD Zen Minimalista**](file:///G:/Mi%20unidad/08_Programas%20PC/10_Asistente-de-reunion/doc/03_modo_hud_zen.md)
   - Filosofía de diseño de la cápsula de 52 px, widget de onda reactiva animada (`AudioWavePulseWidget`), indicador dinámico de interlocutor y transcript colapsable.
4. [**04. Guía de Uso y Configuración**](file:///G:/Mi%20unidad/08_Programas%20PC/10_Asistente-de-reunion/doc/04_guia_de_uso_y_atajos.md)
   - Métodos de ejecución, temas visuales, ajustes de sensibilidad, conexión con Ollama y solución de problemas comunes.
