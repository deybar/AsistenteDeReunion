# 🧘 03. Modo HUD Zen Minimalista

El **Modo HUD Zen** resuelve uno de los mayores problemas identificados en las herramientas de transcripción convencionales: **la distracción visual y la saturación cognitiva**.

---

## 💡 Filosofía de Diseño

Durante una videollamada de trabajo o reunión ejecutiva, el usuario necesita:
1. **Atención plena en la llamada:** No leer paredes de texto que se desplazan sin cesar.
2. **Certeza inmediata de captura:** Saber con solo un vistazo periférico que la herramienta está escuchando y procesando.
3. **Mínimo consumo visual y gráfico:** Ocupar el menor espacio posible en pantalla y no bloquear ventanas de Teams, Zoom o IDEs.

---

## 🎨 Elementos Visuales del HUD Zen

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⠿ [🎙️ Asistente]  [ ▃▆█▃ ]  [⏱️ 04:12]  [🎙️ Tú]   [✨ Minuta] [📜 Texto ▾] [⚙] │
└─────────────────────────────────────────────────────────────────────────────┘
  (Cápsula de 52 px de altura, translúcida, esquinas redondeadas R=14)
```

### 1. Indicador de Arrastre `⠿`
Permite mover la cápsula libremente a cualquier posición de la pantalla con el ratón. La posición se conserva en memoria.

### 2. Onda Reactiva de Audio (`AudioWavePulseWidget`)
- Consta de **5 barras ecualizadoras simétricas** calculadas matemáticamente con curva gaussiana.
- **En reposo / silencio:** Las barras se mantienen en su altura mínima con un brillo cian translúcido tenue (`#38bdf8` al 45% de opacidad).
- **Al detectar voz:** Las barras suben de altura suavemente en tiempo real (animación a 30 FPS) y cambian a un tono esmeralda brillante (`#10b981`), indicando actividad sonora confirmada.
- Suavizado por inercia (*falloff decay*) para que el movimiento sea fluido y natural.

### 3. Cronómetro de Sesión (`⏱️ MM:SS`)
Indica la duración exacta de la reunión y del archivo de audio `.wav` que se está grabando.

### 4. Badge Dinámico de Interlocutor
Cambia en tiempo real según quién esté interviniendo:
- `[🎙️ Tú]` en color azul suave cuando hablas por el micrófono.
- `[🔊 Colegas]` en color cian cuando alguien habla en la videollamada.

### 5. Botón de Minuta Rápida `[✨ Minuta]`
Invoca al Agente Inteligente para consolidar inmediatamente el resumen ejecutivo, compromisos y decisiones técnicas hasta el momento.

### 6. Despliegue de Transcripción Bajo Demanda `[📜 Texto ▾/▴]`
- Por defecto, el área de texto está colapsada (`52 px`).
- Al hacer clic en `[📜 Texto ▾]`, la cápsula se expande verticalmente mostrando el navegador de intervenciones pasadas.
- Al volver a hacer clic en `[📜 Texto ▴]`, regresa a su estado Zen compacto.
