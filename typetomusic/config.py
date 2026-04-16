"""
Configuration management for TypeToMusic.
Handles persistent user settings via JSON config file.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = os.path.expanduser("~/.config/typetomusic")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Default SoundFont search paths (Ubuntu / Linux Mint)
SOUNDFONT_SEARCH_PATHS = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    os.path.expanduser("~/.local/share/typetomusic/soundfonts/FluidR3_GM.sf2"),
    os.path.expanduser("~/.local/share/soundfonts/FluidR3_GM.sf2"),
    "/usr/share/TimGM6mb.sf2",
]


def find_soundfont() -> Optional[str]:
    """Search common paths for a usable SoundFont file."""
    for path in SOUNDFONT_SEARCH_PATHS:
        if os.path.isfile(path):
            logger.info(f"Found SoundFont: {path}")
            return path
    logger.warning("No SoundFont found in default locations.")
    return None


@dataclass
class AppConfig:
    """All persistent application settings."""

    # Audio
    soundfont_path: str = field(default_factory=lambda: find_soundfont() or "")
    instrument_program: int = 0          # GM program number (0 = Acoustic Grand Piano)
    instrument_channel: int = 0
    volume: int = 90                     # 0–127 MIDI velocity ceiling
    audio_driver: str = "auto"          # auto | pipewire | pulseaudio | alsa | jack
    sample_rate: int = 44100
    buffer_size: int = 64                # frames per buffer (latency tuning)
    reverb: bool = True
    chorus: bool = False
    audio_backend: str = "auto"         # auto | fluidsynth | silent

    # Musical
    scale: str = "major"                 # major | minor | pentatonic | chromatic
    root_note: int = 60                  # MIDI note for root (60 = C4)
    octave_range: int = 3                # how many octaves the key mapping spans

    # Keyboard
    input_backend: str = "auto"         # auto | pynput | evdev | limited
    velocity_from_speed: bool = True     # typing speed affects note velocity
    velocity_decay_ms: int = 300         # ms window for speed measurement
    note_duration_ms: int = 120          # how long each note plays (ms)
    sustain_on_hold: bool = False        # sustain while key is held

    # UI
    window_width: int = 480
    window_height: int = 560
    theme: str = "dark"
    show_visualizer: bool = True

    # Logging
    log_level: str = "INFO"

    # ── Serialization ──────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk, falling back to defaults."""
        if not os.path.isfile(CONFIG_FILE):
            logger.info("No config file found; using defaults.")
            return cls()
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            obj = cls()
            for key, value in data.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            logger.info(f"Config loaded from {CONFIG_FILE}")
            return obj
        except Exception as exc:
            logger.error(f"Failed to load config: {exc}. Using defaults.")
            return cls()

    def save(self) -> None:
        """Persist current config to disk."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(asdict(self), f, indent=2)
            logger.debug(f"Config saved to {CONFIG_FILE}")
        except Exception as exc:
            logger.error(f"Failed to save config: {exc}")


# ── GM Instrument Presets ──────────────────────────────────────────────────

GM_INSTRUMENTS = [
    (0,   "Acoustic Grand Piano"),
    (4,   "Electric Piano 1"),
    (8,   "Celesta"),
    (11,  "Vibraphone"),
    (12,  "Marimba"),
    (13,  "Xylophone"),
    (14,  "Tubular Bells"),
    (19,  "Church Organ"),
    (24,  "Acoustic Guitar (nylon)"),
    (25,  "Acoustic Guitar (steel)"),
    (32,  "Acoustic Bass"),
    (40,  "Violin"),
    (46,  "Orchestral Harp"),
    (48,  "String Ensemble 1"),
    (52,  "Choir Aahs"),
    (56,  "Trumpet"),
    (60,  "French Horn"),
    (65,  "Alto Sax"),
    (73,  "Flute"),
    (80,  "Synth Lead (square)"),
    (88,  "Synth Pad (new age)"),
    (98,  "FX 3 (crystal)"),
    (108, "Kalimba"),
    (114, "Steel Drums"),
]

# ── Scale Definitions ──────────────────────────────────────────────────────

SCALES = {
    "major":        [0, 2, 4, 5, 7, 9, 11],
    "minor":        [0, 2, 3, 5, 7, 8, 10],
    "pentatonic":   [0, 2, 4, 7, 9],
    "chromatic":    list(range(12)),
    "blues":        [0, 3, 5, 6, 7, 10],
    "dorian":       [0, 2, 3, 5, 7, 9, 10],
    "lydian":       [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":   [0, 2, 4, 5, 7, 9, 10],
    "whole_tone":   [0, 2, 4, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
              "F#", "G", "G#", "A", "A#", "B"]
