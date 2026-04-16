# 🎹 TypeToMusic

> **Turn your keyboard into a musical instrument.**
> Every keystroke plays a real MIDI note in real time — system-wide, low-latency, and fully configurable.

![Platform](https://img.shields.io/badge/platform-Linux%20%28Ubuntu%2FMint%29-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## What Is TypeToMusic?

TypeToMusic is a Linux desktop application that captures every key you press — anywhere on the system — and plays a corresponding MIDI note through FluidSynth. The faster you type, the louder the notes. Choose your scale, instrument, and root note to turn ordinary typing into an ambient music experience.

**Key highlights:**

- **Global key capture** — works in any application, browser, terminal
- **Real-time, low-latency MIDI** — FluidSynth with PulseAudio/ALSA
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

| Package                                      | Purpose                        |
| -------------------------------------------- | ------------------------------ |
| `python3` (≥ 3.9)                            | Runtime                        |
| `fluidsynth` + `python3-fluidsynth`          | MIDI synthesis + Python bridge |
| `fluid-soundfont-gm` or `timgm6mb-soundfont` | Default GM SoundFont           |
| `python3-pyqt5`                              | GUI framework                  |
| `python3-pynput`                             | System-wide key capture        |

### Python packages

| Package        | Purpose                    |
| -------------- | -------------------------- |
| `PyQt5`        | GUI                        |
| `pynput`       | System-wide key capture    |
| `pyfluidsynth` | FluidSynth Python bindings |

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

The installer:

- Installs all system packages via `apt`
- Creates a Python virtual environment
- Adds a desktop shortcut to your app menu

---

## Manual Installation

### Step 1 — Install system dependencies

```bash
sudo apt update
sudo apt install -y \
    python3 python3-pyqt5 python3-pynput \
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
│   ├── audio_engine.py          # FluidSynth wrapper (threaded)
│   ├── keyboard_listener.py     # Global pynput key capture + velocity tracker
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
    └── deb/
        ├── DEBIAN/
        │   ├── control          # Package metadata
        │   └── postinst         # Post-install hook
        └── usr/
            ├── bin/typetomusic  # Shell launcher
            └── share/
                └── applications/typetomusic.desktop
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      GUI Thread (Qt)                    │
│  MainWindow  ←signals→  AppController                   │
│     │                        │                          │
│  NoteVisualiser          ScaleMapper                     │
│  StatusLED               VelocityTracker                 │
└────────────────────────────┬────────────────────────────┘
                             │ thread-safe callbacks
         ┌───────────────────┼───────────────────┐
         │                   │                   │
┌────────▼───────┐  ┌────────▼────────┐         │
│ Keyboard Thread│  │  Audio Thread   │         │
│  (pynput)      │  │  (FluidSynth)   │         │
│                │  │                 │         │
│ on_press(key)  │  │  cmd_queue      │         │
│       │        │  │  NOTE_ON        │         │
│       └────────┼─►│  NOTE_OFF       │         │
│                │  │  SET_INSTRUMENT │         │
└────────────────┘  └─────────────────┘         │
                                                 │
                              Timer threads (note-off scheduling)
```

**Design decisions:**

- **PyQt5** chosen over PySide6 for its wider Ubuntu/Mint package availability (`python3-pyqt5` in apt). PySide6 requires pip-only install which is heavier for distribution.
- **FluidSynth** runs on a dedicated thread with a bounded command queue to prevent any audio call from blocking the GUI.
- **pynput** runs its own daemon thread. Key events are dispatched via callbacks (not polling), keeping CPU near 0% at idle.
- **Note-off scheduling** uses lightweight `threading.Timer` objects (one per note) rather than a single scheduler thread, keeping code simple and latency low.
- **Scale mapper** assigns a stable index to each unique key string. The same key always produces the same note within a session, making the sound feel musical rather than random.

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
  "audio_driver": "pulseaudio",
  "scale": "major",
  "root_note": 60,
  "octave_range": 3,
  "velocity_from_speed": true,
  "note_duration_ms": 120
}
```

**Audio drivers:** `pulseaudio` (default) → `alsa` → `sdl2` (auto-fallback)

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
System dependencies are resolved automatically by apt.

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

### Audio driver error

Edit `~/.config/typetomusic/config.json` and change `audio_driver` to `"alsa"`:

```json
{ "audio_driver": "alsa" }
```

### Keys not captured globally

TypeToMusic uses `pynput` which requires access to X11 input events.

- Make sure you are running an **X11** session (not Wayland)
- Check: `echo $XDG_SESSION_TYPE` → should print `x11`
- On Wayland, global capture requires elevated permissions

### High latency

Reduce buffer size in config:

```json
{ "buffer_size": 32, "audio_driver": "alsa" }
```

Or install `jackd` and set `"audio_driver": "jack"` for ultra-low latency.

### PyFluidSynth import error

```bash
# Ensure libfluidsynth is installed
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
