"""Keyboard input for TypeToMusic with graceful fallback."""

from __future__ import annotations

import logging
import os
import select
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)

KeyEventCallback = Callable[[str, int], None]


class InputMode(str, Enum):
    FULL = "full"
    LIMITED = "limited"


@dataclass
class InputBackendInfo:
    name: str
    mode: InputMode
    available: bool
    warning: str = ""


def detect_session_type() -> str:
    return os.environ.get("XDG_SESSION_TYPE", "unknown").strip().lower()


_IGNORED_KEYS = frozenset([
    "ctrl_l", "ctrl_r", "alt_l", "alt_r", "alt_gr",
    "shift", "shift_r", "caps_lock", "super_l", "super_r",
    "num_lock", "scroll_lock",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "print_screen", "pause", "insert", "delete",
    "home", "end", "page_up", "page_down",
    "up", "down", "left", "right",
    "media_play_pause", "media_next", "media_previous",
    "volume_up", "volume_down", "volume_mute",
])


def _key_to_str(key) -> Optional[str]:
    try:
        return key.char if key.char else None
    except AttributeError:
        name = key.name.lower() if hasattr(key, "name") else ""
        return name if name and name not in _IGNORED_KEYS else None


class VelocityTracker:
    def __init__(self, window_ms: int = 300, base_velocity: int = 90):
        self._window_ms = window_ms
        self._base_velocity = base_velocity
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def record_keypress(self) -> int:
        now = time.monotonic()
        window = self._window_ms / 1000.0
        with self._lock:
            self._timestamps.append(now)
            while self._timestamps and (now - self._timestamps[0]) > window:
                self._timestamps.popleft()
            count = len(self._timestamps)
        velocity = int(50 + (count / 5.0) * 77)
        return max(40, min(127, velocity))

    def set_base_velocity(self, v: int) -> None:
        self._base_velocity = max(1, min(127, v))

    def set_window(self, ms: int) -> None:
        self._window_ms = max(50, ms)


class _BaseInputBackend:
    name = "base"
    mode = InputMode.LIMITED

    def __init__(self, callback: KeyEventCallback, velocity_tracker: Optional[VelocityTracker] = None,
                 use_speed_velocity: bool = True, fixed_velocity: int = 90):
        self._callback = callback
        self._velocity_tracker = velocity_tracker or VelocityTracker()
        self._use_speed_velocity = use_speed_velocity
        self._fixed_velocity = fixed_velocity
        self._running = False
        self._warning = ""

    def start(self) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        self._running = False

    @property
    def info(self) -> InputBackendInfo:
        return InputBackendInfo(self.name, self.mode, self._running, self._warning)

    def _emit(self, key_str: str) -> None:
        velocity = self._velocity_tracker.record_keypress() if self._use_speed_velocity else self._fixed_velocity
        try:
            self._callback(key_str, velocity)
        except (TypeError, ValueError, RuntimeError) as exc:
            logger.error("Input backend callback error: %s", exc)


class PynputInputBackend(_BaseInputBackend):
    name = "pynput"
    mode = InputMode.FULL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard as pynput_kb
        except ImportError:
            self._warning = "pynput is not installed."
            logger.warning(self._warning)
            return False

        try:
            self._listener = pynput_kb.Listener(on_press=self._on_press, suppress=False)
            self._listener.start()
            self._running = True
            logger.info("KeyboardListener started using pynput.")
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            self._warning = f"pynput backend failed: {exc}"
            logger.warning(self._warning)
            return False

    def stop(self) -> None:
        if self._listener and self._running:
            try:
                self._listener.stop()
            except (OSError, RuntimeError, ValueError):
                pass
        super().stop()

    def _on_press(self, key) -> None:
        key_str = _key_to_str(key)
        if key_str is not None:
            self._emit(key_str)


class EvdevInputBackend(_BaseInputBackend):
    name = "evdev"
    mode = InputMode.FULL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._device = None
        self._key_codes: dict[int, str] = {}

    def start(self) -> bool:
        try:
            from evdev import InputDevice, ecodes, list_devices
        except ImportError:
            self._warning = "evdev is not installed."
            logger.warning(self._warning)
            return False

        self._key_codes = {
            code: name.replace("KEY_", "").lower()
            for name, code in ecodes.KEY.items()
            if isinstance(code, int) and name.startswith("KEY_")
        }

        for path in list_devices():
            try:
                device = InputDevice(path)
                if ecodes.EV_KEY not in device.capabilities():
                    continue
                self._device = device
                break
            except (OSError, RuntimeError, ValueError):
                continue

        if self._device is None:
            self._warning = "No readable keyboard device found for evdev."
            logger.warning(self._warning)
            return False

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="EvdevInput", daemon=True)
        self._thread.start()
        self._running = True
        logger.info("KeyboardListener started using evdev on %s.", self._device.path)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._device is not None:
            try:
                self._device.close()
            except (OSError, RuntimeError, ValueError):
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        super().stop()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set() and self._device is not None:
                ready, _, _ = select.select([self._device.fd], [], [], 0.25)
                if self._device.fd not in ready:
                    continue
                for event in self._device.read():
                    if getattr(event, "type", None) != 1 or getattr(event, "value", None) != 1:
                        continue
                    key_str = self._key_codes.get(event.code)
                    if key_str and key_str not in _IGNORED_KEYS:
                        self._emit(key_str)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning("evdev backend stopped: %s", exc)
        finally:
            self._running = False


class LimitedInputBackend(_BaseInputBackend):
    name = "limited"
    mode = InputMode.LIMITED

    def start(self) -> bool:
        self._warning = (
            "Global keyboard capture is unavailable for this session. "
            "The app is running in limited mode."
        )
        self._running = True
        logger.warning(self._warning)
        return True


class KeyboardListener:
    def __init__(
        self,
        callback: KeyEventCallback,
        velocity_tracker: Optional[VelocityTracker] = None,
        use_speed_velocity: bool = True,
        fixed_velocity: int = 90,
        backend_hint: str = "auto",
    ):
        self._callback = callback
        self._velocity_tracker = velocity_tracker or VelocityTracker()
        self._use_speed_velocity = use_speed_velocity
        self._fixed_velocity = fixed_velocity
        self._backend_hint = backend_hint
        self._backend: Optional[_BaseInputBackend] = None
        self._running = False

    def _backend_order(self) -> list[str]:
        hint = (self._backend_hint or "auto").strip().lower()
        session = detect_session_type()
        if hint in {"pynput", "evdev", "limited"}:
            return [hint]
        if session == "wayland":
            return ["evdev", "pynput", "limited"]
        return ["pynput", "evdev", "limited"]

    def _create_backend(self, name: str) -> _BaseInputBackend:
        if name == "pynput":
            return PynputInputBackend(self._callback, self._velocity_tracker, self._use_speed_velocity, self._fixed_velocity)
        if name == "evdev":
            return EvdevInputBackend(self._callback, self._velocity_tracker, self._use_speed_velocity, self._fixed_velocity)
        return LimitedInputBackend(self._callback, self._velocity_tracker, self._use_speed_velocity, self._fixed_velocity)

    def start(self) -> bool:
        if self._running:
            return True
        for backend_name in self._backend_order():
            backend = self._create_backend(backend_name)
            if backend.start():
                self._backend = backend
                self._running = True
                if backend.info.mode == InputMode.LIMITED:
                    logger.warning(backend.info.warning)
                return True
        self._backend = LimitedInputBackend(self._callback, self._velocity_tracker, self._use_speed_velocity, self._fixed_velocity)
        self._backend.start()
        self._running = True
        return True

    def stop(self) -> None:
        if self._backend:
            self._backend.stop()
        self._running = False
        logger.info("KeyboardListener stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> InputMode:
        if self._backend:
            return self._backend.info.mode
        return InputMode.LIMITED

    @property
    def warning(self) -> str:
        if self._backend:
            return self._backend.info.warning
        return ""

    def set_velocity_mode(self, use_speed: bool, fixed: int = 90) -> None:
        self._use_speed_velocity = use_speed
        self._fixed_velocity = max(1, min(127, fixed))
        if self._backend:
            self._backend._use_speed_velocity = self._use_speed_velocity
            self._backend._fixed_velocity = self._fixed_velocity
