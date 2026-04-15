"""
Keyboard Listener for TypeToMusic.
Uses pynput for system-wide (global) key capture on X11.
Emits key events via a callback and measures typing speed
to modulate note velocity.
"""

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Typing: callback receives (key_char: str, velocity: int)
KeyEventCallback = Callable[[str, int], None]

# Keys to ignore (modifiers, function keys, etc.)
_IGNORED_KEYS = frozenset([
    "ctrl_l", "ctrl_r", "alt_l", "alt_r", "alt_gr",
    "shift", "shift_r", "caps_lock", "super_l", "super_r",
    "num_lock", "scroll_lock",
    "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12",
    "print_screen", "pause", "insert", "delete",
    "home", "end", "page_up", "page_down",
    "up", "down", "left", "right",
    "media_play_pause", "media_next", "media_previous",
    "volume_up", "volume_down", "volume_mute",
])


def _key_to_str(key) -> Optional[str]:
    """Normalise a pynput Key or KeyCode to a string identifier."""
    try:
        # Regular character key
        return key.char if key.char else None
    except AttributeError:
        # Special key
        name = key.name.lower() if hasattr(key, "name") else ""
        return name if name and name not in _IGNORED_KEYS else None


class VelocityTracker:
    """
    Measures typing speed over a rolling time window.
    Returns a MIDI velocity (1–127) proportional to WPM.
    """

    def __init__(self, window_ms: int = 300, base_velocity: int = 90):
        self._window_ms    = window_ms
        self._base_velocity = base_velocity
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def record_keypress(self) -> int:
        """Record a keypress and return the current velocity (1–127)."""
        now = time.monotonic()
        window = self._window_ms / 1000.0

        with self._lock:
            self._timestamps.append(now)
            # Purge timestamps outside the window
            while self._timestamps and (now - self._timestamps[0]) > window:
                self._timestamps.popleft()
            count = len(self._timestamps)

        # Map count-per-window to velocity
        # 1 key/window → 60; 5+ keys/window → 127
        velocity = int(50 + (count / 5.0) * 77)
        velocity = max(40, min(127, velocity))
        return velocity

    def set_base_velocity(self, v: int) -> None:
        self._base_velocity = max(1, min(127, v))

    def set_window(self, ms: int) -> None:
        self._window_ms = max(50, ms)


class KeyboardListener:
    """
    System-wide keyboard listener using pynput.
    Runs on its own daemon thread.
    Calls `callback(key_str, velocity)` for every captured key press.
    """

    def __init__(
        self,
        callback: KeyEventCallback,
        velocity_tracker: Optional[VelocityTracker] = None,
        use_speed_velocity: bool = True,
        fixed_velocity: int = 90,
    ):
        self._callback           = callback
        self._velocity_tracker   = velocity_tracker or VelocityTracker()
        self._use_speed_velocity = use_speed_velocity
        self._fixed_velocity     = fixed_velocity
        self._listener           = None
        self._running            = False
        self._key_index          = 0
        self._key_index_map: dict[str, int] = {}
        self._lock               = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start the global key listener. Returns True on success."""
        if self._running:
            return True
        try:
            from pynput import keyboard as pynput_kb
        except ImportError:
            logger.error(
                "pynput not installed. Run: pip install pynput"
            )
            return False

        try:
            self._listener = pynput_kb.Listener(
                on_press=self._on_press,
                suppress=False,      # Never suppress – we are an observer only
            )
            self._listener.start()
            self._running = True
            logger.info("KeyboardListener started (global capture active).")
            return True
        except Exception as exc:
            logger.error(f"Failed to start keyboard listener: {exc}")
            return False

    def stop(self) -> None:
        """Stop the listener."""
        if self._listener and self._running:
            try:
                self._listener.stop()
            except Exception:
                pass
        self._running = False
        logger.info("KeyboardListener stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def set_velocity_mode(self, use_speed: bool, fixed: int = 90) -> None:
        self._use_speed_velocity = use_speed
        self._fixed_velocity     = max(1, min(127, fixed))

    # ── Internal ──────────────────────────────────────────────────────────

    def _on_press(self, key) -> None:
        """pynput callback – called on every key press."""
        key_str = _key_to_str(key)
        if key_str is None:
            return  # Ignored key

        if self._use_speed_velocity:
            velocity = self._velocity_tracker.record_keypress()
        else:
            velocity = self._fixed_velocity

        with self._lock:
            # Assign a stable index to each unique key string
            if key_str not in self._key_index_map:
                self._key_index_map[key_str] = len(self._key_index_map)

        try:
            self._callback(key_str, velocity)
        except Exception as exc:
            logger.error(f"KeyboardListener callback error: {exc}")
