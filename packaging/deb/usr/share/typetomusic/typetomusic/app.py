"""
TypeToMusic Application Controller.
Wires together the keyboard listener, scale mapper, and audio engine.
Exposes a clean interface to the GUI layer.
"""

import logging
import threading
from typing import Optional, Callable

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QMainWindow

from .config import AppConfig, GM_INSTRUMENTS
from .audio_engine import AudioEngine
from .keyboard_listener import KeyboardListener, VelocityTracker
from .scale_mapper import ScaleMapper
from .gui import MainWindow

logger = logging.getLogger(__name__)


class AppController(QObject):
    """
    Central controller that owns and coordinates all subsystems.
    The GUI connects to signals on this object.
    """

    # Signals emitted to update the GUI
    status_changed  = pyqtSignal(str, str)   # (message, level: ok|warn|error)
    note_played     = pyqtSignal(int, int)   # (midi_note, velocity)
    engine_ready    = pyqtSignal(bool)       # True = ready, False = error

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config  = config
        self._active  = False
        self._lock    = threading.Lock()

        # Sub-systems (created lazily)
        self._audio:    Optional[AudioEngine]     = None
        self._listener: Optional[KeyboardListener] = None
        self._velocity: VelocityTracker            = VelocityTracker(
            window_ms=config.velocity_decay_ms
        )
        self._mapper: ScaleMapper = ScaleMapper(
            scale_name=config.scale,
            root_note=config.root_note,
            octave_range=config.octave_range,
        )

        # Key → index counter (deterministic note assignment)
        self._key_order: list[str] = []
        self._key_map:   dict[str, int] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def initialise_audio(self) -> bool:
        """Start the audio engine. Returns True on success."""
        if not self._config.soundfont_path:
            msg = "No SoundFont configured. Please set a SoundFont path."
            logger.error(msg)
            self.status_changed.emit(msg, "error")
            self.engine_ready.emit(False)
            return False

        self._audio = AudioEngine(
            soundfont_path=self._config.soundfont_path,
            audio_driver=self._config.audio_driver,
            sample_rate=self._config.sample_rate,
            buffer_size=self._config.buffer_size,
            reverb=self._config.reverb,
            chorus=self._config.chorus,
        )
        ok = self._audio.start()
        if ok:
            self._audio.set_instrument(
                self._config.instrument_program,
                self._config.instrument_channel,
            )
            self._audio.set_volume(self._config.volume)
            self.status_changed.emit("Audio engine ready.", "ok")
            self.engine_ready.emit(True)
            logger.info("Audio engine started successfully.")
        else:
            err = self._audio.error or "Unknown audio error."
            self.status_changed.emit(f"Audio error: {err}", "error")
            self.engine_ready.emit(False)
            logger.error(f"Audio engine failed: {err}")
        return ok

    def start_listening(self) -> bool:
        """Enable global keyboard capture and music playback."""
        if self._active:
            return True
        if not self._audio or not self._audio.is_ready:
            if not self.initialise_audio():
                return False

        self._listener = KeyboardListener(
            callback=self._on_key,
            velocity_tracker=self._velocity,
            use_speed_velocity=self._config.velocity_from_speed,
            fixed_velocity=self._config.volume,
        )
        ok = self._listener.start()
        if ok:
            self._active = True
            self.status_changed.emit("Listening – start typing!", "ok")
            logger.info("Keyboard listening started.")
        else:
            self.status_changed.emit("Failed to start keyboard capture.", "error")
            logger.error("Keyboard listener failed to start.")
        return ok

    def stop_listening(self) -> None:
        """Disable keyboard capture and silence all notes."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._audio:
            self._audio.all_notes_off()
        self._active = False
        self.status_changed.emit("Stopped.", "warn")
        logger.info("Keyboard listening stopped.")

    def shutdown(self) -> None:
        """Full cleanup – called on app exit."""
        self.stop_listening()
        if self._audio:
            self._audio.stop()
            self._audio = None
        self._config.save()
        logger.info("AppController shutdown complete.")

    # ── Setting changes (called from GUI) ─────────────────────────────────

    def set_instrument(self, program: int) -> None:
        self._config.instrument_program = program
        if self._audio:
            self._audio.set_instrument(program, self._config.instrument_channel)
        logger.debug(f"Instrument set to program {program}")

    def set_scale(self, scale_name: str) -> None:
        self._config.scale = scale_name
        self._mapper.update(scale_name=scale_name)
        # Reset key mapping so new scale applies from index 0
        self._reset_key_mapping()
        logger.debug(f"Scale changed to {scale_name}")

    def set_root_note(self, midi_note: int) -> None:
        self._config.root_note = midi_note
        self._mapper.update(root_note=midi_note)
        self._reset_key_mapping()

    def set_volume(self, volume: int) -> None:
        self._config.volume = volume
        if self._audio:
            self._audio.set_volume(volume)

    def set_velocity_from_speed(self, enabled: bool) -> None:
        self._config.velocity_from_speed = enabled
        if self._listener:
            self._listener.set_velocity_mode(enabled, self._config.volume)

    def set_soundfont(self, path: str) -> None:
        was_active = self._active
        if was_active:
            self.stop_listening()
        if self._audio:
            self._audio.stop()
            self._audio = None
        self._config.soundfont_path = path
        if was_active:
            self.start_listening()

    # ── Internal ──────────────────────────────────────────────────────────

    def _on_key(self, key_str: str, velocity: int) -> None:
        """
        Called from the keyboard listener thread for every captured key.
        Maps key → note index → MIDI note, then sends to audio engine.
        """
        with self._lock:
            if key_str not in self._key_map:
                self._key_map[key_str] = len(self._key_order)
                self._key_order.append(key_str)
            index = self._key_map[key_str]

        note = self._mapper.note_for_index(index)
        self._audio.play_note(
            note=note,
            velocity=velocity,
            channel=self._config.instrument_channel,
            duration_ms=self._config.note_duration_ms,
        )
        # Signal to GUI (thread-safe via Qt queued connection)
        self.note_played.emit(note, velocity)

    def _reset_key_mapping(self) -> None:
        """Reset key → index mapping so scale changes feel immediate."""
        with self._lock:
            self._key_map.clear()
            self._key_order.clear()


class TypeToMusicApp(QMainWindow):
    """
    Top-level QMainWindow.  Creates the controller and the GUI,
    wires signals, and handles the application lifecycle.
    """

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config     = config
        self._controller = AppController(config, parent=self)
        self._window     = MainWindow(config, self._controller, parent=self)
        self.setCentralWidget(self._window)

        self.setWindowTitle("TypeToMusic")
        self.setFixedSize(config.window_width, config.window_height)
        self._apply_window_style()

        # Auto-initialise audio shortly after GUI appears
        QTimer.singleShot(300, self._controller.initialise_audio)

    def closeEvent(self, event):
        self._controller.shutdown()
        event.accept()

    def _apply_window_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #0d0d12;
            }
        """)
