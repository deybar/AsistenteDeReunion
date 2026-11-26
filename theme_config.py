"""
Configuración de Temas Visuales y Persistencia para el Asistente de Reuniones.
Diseño moderno, traslúcido y de alto contraste cinematográfico.
"""

import json
import os
from typing import Dict, Any

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

# Paletas de 5 temas elegantes de alta legibilidad
THEMES: Dict[str, Dict[str, str]] = {
    "dark_carbon": {
        "name": "Oscuro Carbón (Cine)",
        "card_bg": "#121214",
        "card_bg_rgb": "18, 18, 20",
        "text_main": "#f4f4f5",
        "text_muted": "#a1a1aa",
        "text_accent": "#38bdf8",      # Celeste cian
        "speaker_self": "#10b981",     # Verde esmeralda para [Tú]
        "speaker_other": "#60a5fa",    # Azul claro para [Participantes]
        "action_item_color": "#fbbf24", # Ámbar para compromisos
        "border": "#27272a",
        "btn_bg": "#18181b",
        "btn_bg_hover": "#27272a",
        "btn_border": "#3f3f46",
        "btn_accent_bg": "#0284c7",
        "btn_accent_hover": "#0369a1",
        "badge_bg": "#27272a"
    },
    "dark_slate": {
        "name": "Oscuro Gris (Grafito)",
        "card_bg": "#0f172a",
        "card_bg_rgb": "15, 23, 42",
        "text_main": "#f8fafc",
        "text_muted": "#94a3b8",
        "text_accent": "#818cf8",      # Índigo
        "speaker_self": "#34d399",     # Verde menta
        "speaker_other": "#38bdf8",    # Celeste
        "action_item_color": "#f59e0b",
        "border": "#1e293b",
        "btn_bg": "#1e293b",
        "btn_bg_hover": "#334155",
        "btn_border": "#475569",
        "btn_accent_bg": "#4f46e5",
        "btn_accent_hover": "#4338ca",
        "badge_bg": "#1e293b"
    },
    "dark_mocha": {
        "name": "Oscuro Moca Cálido",
        "card_bg": "#1c1917",
        "card_bg_rgb": "28, 25, 23",
        "text_main": "#fafaf9",
        "text_muted": "#a8a29e",
        "text_accent": "#f59e0b",      # Ámbar cálido
        "speaker_self": "#4ade80",     # Verde
        "speaker_other": "#fb923c",    # Naranja
        "action_item_color": "#fbbf24",
        "border": "#292524",
        "btn_bg": "#292524",
        "btn_bg_hover": "#44403c",
        "btn_border": "#57534e",
        "btn_accent_bg": "#d97706",
        "btn_accent_hover": "#b45309",
        "badge_bg": "#292524"
    },
    "dark_midnight": {
        "name": "Oscuro Noche (Midnight)",
        "card_bg": "#0b0f19",
        "card_bg_rgb": "11, 15, 25",
        "text_main": "#f1f5f9",
        "text_muted": "#64748b",
        "text_accent": "#06b6d4",      # Turquesa
        "speaker_self": "#10b981",
        "speaker_other": "#3b82f6",
        "action_item_color": "#eab308",
        "border": "#1e293b",
        "btn_bg": "#111827",
        "btn_bg_hover": "#1f2937",
        "btn_border": "#374151",
        "btn_accent_bg": "#0891b2",
        "btn_accent_hover": "#0e7490",
        "badge_bg": "#1e293b"
    },
    "nord_light": {
        "name": "Claro Suave (Nord)",
        "card_bg": "#eceff4",
        "card_bg_rgb": "236, 239, 244",
        "text_main": "#2e3440",
        "text_muted": "#4c566a",
        "text_accent": "#5e81ac",
        "speaker_self": "#2e7d32",
        "speaker_other": "#1565c0",
        "action_item_color": "#d97706",
        "border": "#d8dee9",
        "btn_bg": "#e5e9f0",
        "btn_bg_hover": "#d8dee9",
        "btn_border": "#c8d0e0",
        "btn_accent_bg": "#5e81ac",
        "btn_accent_hover": "#4c566a",
        "badge_bg": "#d8dee9"
    }
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "theme": "dark_carbon",
    "opacity": 92,
    "font_size": 15,
    "model_size": "base",              # "tiny", "base", "small" (multilingües)
    "latency_mode": "ultra_fast",      # "ultra_fast", "balanced", "extended"
    "language": "es",                  # "es", "auto", "en"
    "audio_mode": "mixed",             # "mixed" (PC + Mic), "loopback" (solo PC), "microphone" (solo Mic)
    "loopback_device_index": None,
    "mic_device_index": None,
    "user_label": "Tú",               # Etiqueta para el micrófono del usuario
    "auto_extract_summary": True,      # Activar agente al finalizar sesión
    "ollama_enabled": True,            # Si Ollama está disponible, usarlo opcionalmente
    "ollama_model": "qwen2.5:3b",      # Modelo ligero y preciso para Ollama
    "ollama_url": "http://localhost:11434",
    "save_dir": "reuniones",
    "window_pos_x": 100,
    "window_pos_y": 680,
    "window_width": 940,
    "window_height": 210,
    "tools_expanded": True,
    "is_pinned": True
}

def load_config() -> Dict[str, Any]:
    """Carga la configuración persistente desde config.json o devuelve valores por defecto."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]):
    """Guarda la configuración en disco en formato JSON."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Error al guardar config.json: {e}")

def get_theme_data(theme_key: str) -> Dict[str, str]:
    """Retorna el diccionario de colores para la clave de tema solicitada."""
    return THEMES.get(theme_key, THEMES["dark_carbon"])
