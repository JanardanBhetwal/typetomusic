# 🎹 TypeToMusic

> **Turn your keyboard into a musical instrument.**
> Every keystroke plays a real MIDI note in real time — system-wide, low-latency, and fully configurable.

![Platform](https://img.shields.io/badge/platform-Linux%20%28Ubuntu%2FMint%29-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## What Is TypeToMusic?

TypeToMusic is a Linux desktop application that turns typing into MIDI music with best-effort global input capture, runtime audio fallback, and graceful limited mode when a desktop session blocks full capture. The faster you type, the louder the notes. Choose your scale, instrument, and root note to turn ordinary typing into an ambient music experience.

**Key highlights:**

- **Global key capture** — X11, Wayland helper, or limited mode fallback
- **Real-time, low-latency MIDI** — FluidSynth with PipeWire / PulseAudio / ALSA fallback
- **Musical scale mapping** — Major, Minor, Pentatonic, Blues, Dorian, and more
- **Typing speed → velocity** — fast typing plays louder notes
- **GM instrument selection** — Piano, Kalimba, Flute, Strings, and 20+ presets
- **Animated visualiser** — ripple waves react to each note
- **No crashes** — threaded architecture, graceful error handling

---

## Screenshots

```
┌─────────────────────────────────────────┐
│ TypeToMusic                      ● Ready │
│ ╔═══════════════════════════════════════╗│
│ ║  ~~~~~ waveform visualiser ~~~~~      ║│
│ ╚═══════════════════════════════════════╝│
│ ▶  START PLAYING                         │
│                                          │
│ Sound ─────────────────────────────────  │
│ Instrument   [Acoustic Grand Piano  ▼]   │
│ Scale  [Major ▼]         Root  [C  ▼]   │
│                                          │
│ Controls ──────────────────────────────  │
│ Volume   [════════●──────]  90           │
│ ☑ Typing speed → note velocity           │
│                                          │
│ SoundFont ─────────────────────────────  │
│ /usr/share/sounds/sf2/FluidR3_GM.sf2     │
│                                 [Browse] │
│                                          │
│        ♪  C4   vel=98                   │
└─────────────────────────────────────────┘
```

---

## Requirements

### System (Ubuntu / Linux Mint)

| Package                                      | Purpose                       |
| -------------------------------------------- | ----------------------------- |
| `python3` (≥ 3.9)                            | Runtime                       |
| `python3-pyqt5`                              | GUI framework                 |
| `python3-pynput` or `python3-evdev`          | Optional input backends       |
| `fluidsynth` + `python3-fluidsynth`          | Optional MIDI synthesis stack |
| `fluid-soundfont-gm` or `timgm6mb-soundfont` | Optional default GM SoundFont |

### Python packages

| Package        | Purpose                      |
| -------------- | ---------------------------- |
| `PyQt5`        | GUI                          |
| `pynput`       | Optional X11 capture         |
| `evdev`        | Optional Wayland / raw input |
| `pyfluidsynth` | Optional FluidSynth bridge   |

---

## Quick Start (Recommended)

```bash
# 1. Clone or unzip the project
cd typetomusic/

# 2. Run the one-command installer
bash scripts/install.sh

# 3. Launch the app
./typetomusic
```

The installer sets up the core app and then enables optional backends when they are available.

---

## Manual Installation

### Step 1 — Install system dependencies

```bash
sudo apt update
sudo apt install -y \
    python3 python3-pyqt5 \
    python3-pynput python3-evdev \
    fluidsynth python3-fluidsynth \
    fluid-soundfont-gm || sudo apt install -y timgm6mb-soundfont
```

### Step 2 — Create a virtual environment (recommended)

```bash
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

### Step 3 — Run

```bash
python3 main.py
```

If optional packages are missing, the app still launches and switches to limited or silent mode instead of failing.

---

## Project Structure

```
typetomusic/
├── main.py                      # Entry point
├── requirements.txt             # Python dependencies
├── setup.py                     # pip-installable package config
├── typetomusic.spec             # PyInstaller build spec
├── README.md
│
├── typetomusic/                 # Main application package
│   ├── __init__.py
│   ├── app.py                   # AppController + TypeToMusicApp (QMainWindow)
│   ├── audio_engine.py          # Audio backend manager with silent fallback
│   ├── keyboard_listener.py     # Input backend manager with limited-mode fallback
│   ├── scale_mapper.py          # Key index → MIDI note mapping
│   ├── config.py                # Persistent JSON config + GM instrument list
│   └── gui.py                   # PyQt5 GUI (MainWindow, visualiser, controls)
│
├── tests/
│   └── test_core.py             # pytest unit tests (no GUI required)
│
├── scripts/
│   ├── install.sh               # End-user one-command installer
│   └── build.sh                 # Build script (run / exe / deb)
│
└── packaging/
    ├── deb/
    │   ├── DEBIAN/
    │   │   ├── control          # Package metadata
    │   │   └── postinst         # Post-install hook
    │   └── usr/
    │       ├── bin/typetomusic  # Shell launcher
    │       └── share/
    │           └── applications/typetomusic.desktop
    ├── rpm/
    │   └── typetomusic.spec     # Fedora/RPM packaging spec
    └── arch/
        └── PKGBUILD             # Arch Linux package recipe
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      GUI Thread (Qt)                    │
│  MainWindow  ←signals→  AppController                   │
│     │                        │                          │
│  NoteVisualiser          StatusLED                      │
│  ScaleMapper             VelocityTracker                │
└────────────────────────────┬────────────────────────────┘
                                      │
                    ┌─────────────┼─────────────┐
                    │                           │
        Input backend manager        Audio backend manager
    (X11 / Wayland / limited)     (FluidSynth / silent)
                    │                           │
                    └─────────────┬─────────────┘
                                      │
                         AppController routes events
```

**Design decisions:**

- **PyQt5** stays the UI layer because it is available across the target distros.
- **Input and audio are abstracted** so optional packages can disappear without breaking launch.
- **Wayland sessions** prefer a safe event-device backend when available and otherwise fall back to limited mode.
- **Audio** prefers FluidSynth with runtime driver fallback, then silent mode if no synth is available.
- **Scale mapper** assigns a stable index to each unique key string so the same key stays musically consistent.

---

## Configuration

Settings are persisted automatically to:

```
~/.config/typetomusic/config.json
```

Key settings you can edit manually:

```json
{
  "soundfont_path": "/usr/share/sounds/sf2/FluidR3_GM.sf2",
  "instrument_program": 0,
  "volume": 90,
  "audio_driver": "auto",
  "scale": "major",
  "root_note": 60,
  "octave_range": 3,
  "velocity_from_speed": true,
  "note_duration_ms": 120
}
```

**Audio drivers:** `auto` → `pipewire` → `pulseaudio` → `alsa` → `jack` → `sdl2` → silent fallback

---

## Building a Standalone Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build (output in dist/TypeToMusic/)
bash scripts/build.sh exe

# Run the standalone binary
./dist/TypeToMusic/typetomusic
```

The binary bundles Python and all dependencies. Share the entire `dist/TypeToMusic/` folder.

---

## Building a .deb Package

```bash
# Requires dpkg-deb (pre-installed on Ubuntu/Mint)
bash scripts/build.sh deb

# Install the package (auto-installs dependencies)
sudo apt install -y ./dist/typetomusic_*_*.deb

# Run
typetomusic
```

Share the generated `.deb` file from `dist/` with other Ubuntu/Mint users.
System dependencies are resolved automatically by apt when available, and missing optional backends only reduce functionality instead of breaking install.

## Cross-Distro Packaging

- `.deb` — Debian, Ubuntu, Mint, Kali
- `.rpm` — Fedora and compatible RPM systems
- `PKGBUILD` — Arch Linux and derivatives
- `pip install` — core app plus optional extras for X11, Wayland, and audio

The rule is simple: only the GUI and Python runtime are hard requirements. Everything else is optional and must fall back cleanly.

---

## Running Tests

```bash
# Install pytest
pip install pytest

# Run tests (no display required)
python -m pytest tests/ -v
```

---

## Troubleshooting

### No sound / FluidSynth error

```bash
# Check FluidSynth is installed
fluidsynth --version

# Check SoundFont exists
ls /usr/share/sounds/sf2/
ls /usr/share/soundfonts/

# Install missing SoundFont
sudo apt install fluid-soundfont-gm || sudo apt install timgm6mb-soundfont
```

If no synth package is available, TypeToMusic still launches in silent mode.

### Audio driver error

Edit `~/.config/typetomusic/config.json` and change `audio_driver` to `"alsa"`:

```json
{ "audio_driver": "alsa" }
```

### Keys not captured globally

TypeToMusic auto-selects the best available input backend.

- On X11, it prefers `pynput`.
- On Wayland, it tries `evdev` if device access is available.
- If neither path is available, it switches to limited mode instead of crashing.

Check your session type with:

```bash
echo $XDG_SESSION_TYPE
```

### High latency

Reduce buffer size in config:

```json
{ "buffer_size": 32, "audio_driver": "alsa" }
```

Or install `jackd` and set `"audio_driver": "jack"` for ultra-low latency.

### PyFluidSynth import error

```bash
# Optional only; the app still runs without it
sudo apt install libfluidsynth-dev

# Reinstall Python bindings
pip install --force-reinstall pyfluidsynth
```

---

## Supported Scales

| Scale          | Intervals                 |
| -------------- | ------------------------- |
| Major          | 0 2 4 5 7 9 11            |
| Minor          | 0 2 3 5 7 8 10            |
| Pentatonic     | 0 2 4 7 9                 |
| Blues          | 0 3 5 6 7 10              |
| Chromatic      | 0 1 2 3 4 5 6 7 8 9 10 11 |
| Dorian         | 0 2 3 5 7 9 10            |
| Lydian         | 0 2 4 6 7 9 11            |
| Mixolydian     | 0 2 4 5 7 9 10            |
| Whole Tone     | 0 2 4 6 8 10              |
| Harmonic Minor | 0 2 3 5 7 8 11            |

---

## License

MIT License — free to use, modify, and distribute.

---

## Contributing

Pull requests welcome. Keep changes focused, add tests for new logic.
