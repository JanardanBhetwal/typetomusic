"""Audio engine for TypeToMusic with graceful silent fallback."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger(__name__)


class AudioMode(str, Enum):
    FULL = "full"
    SILENT = "silent"


class EngineCommand(Enum):
    NOTE_ON = auto()
    NOTE_OFF = auto()
    ALL_NOTES_OFF = auto()
    SET_INSTRUMENT = auto()
    SET_VOLUME = auto()
    SHUTDOWN = auto()


@dataclass
class AudioCommand:
    cmd: EngineCommand
    note: int = 0
    velocity: int = 100
    channel: int = 0
    program: int = 0
    volume: int = 90


class _BaseAudioBackend:
    mode = AudioMode.SILENT

    def __init__(self) -> None:
        self._running = False
        self._warning = ""

    def start(self) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        self._running = False

    def play_note(self, note: int, velocity: int, channel: int = 0, duration_ms: int = 120) -> None:
        return

    def all_notes_off(self) -> None:
        return

    def set_instrument(self, program: int, channel: int = 0) -> None:
        return

    def set_volume(self, volume: int) -> None:
        return

    @property
    def warning(self) -> str:
        return self._warning


class SilentAudioBackend(_BaseAudioBackend):
    mode = AudioMode.SILENT

    def __init__(self, warning: str = "") -> None:
        super().__init__()
        self._warning = warning or "Audio backends unavailable. Running in silent mode."

    def start(self) -> bool:
        self._running = True
        logger.warning(self._warning)
        return True


class FluidSynthAudioBackend(_BaseAudioBackend):
    mode = AudioMode.FULL

    def __init__(
        self,
        soundfont_path: str,
        audio_driver: str = "auto",
        sample_rate: int = 44100,
        buffer_size: int = 64,
        reverb: bool = True,
        chorus: bool = False,
    ) -> None:
        super().__init__()
        self._soundfont_path = soundfont_path
        self._audio_driver = (audio_driver or "auto").strip().lower()
        self._sample_rate = sample_rate
        self._buffer_size = buffer_size
        self._reverb = reverb
        self._chorus = chorus
        self._fs = None
        self._sfid = None
        self._cmd_queue: queue.Queue = queue.Queue(maxsize=512)
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._active_notes: dict[int, set[int]] = {}

    @property
    def error(self) -> Optional[str]:
        return self._error

    def start(self) -> bool:
        if self._running:
            return True
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(target=self._worker, name="AudioEngine", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            self._running = False
            self._error = "Audio backend timed out during startup."
            logger.error(self._error)
            return False
        return self._error is None

    def stop(self) -> None:
        if not self._running:
            return
        try:
            self._cmd_queue.put(AudioCommand(cmd=EngineCommand.SHUTDOWN))
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=3.0)
        self._running = False

    def play_note(self, note: int, velocity: int, channel: int = 0, duration_ms: int = 120) -> None:
        if not self._running or self._error:
            return
        velocity = max(1, min(127, velocity))
        note = max(0, min(127, note))
        try:
            self._cmd_queue.put_nowait(AudioCommand(cmd=EngineCommand.NOTE_ON, note=note, velocity=velocity, channel=channel))
        except queue.Full:
            logger.warning("Audio command queue full; dropping note.")
            return
        timer = threading.Timer(duration_ms / 1000.0, self._enqueue_note_off, args=(note, channel))
        timer.daemon = True
        timer.start()

    def all_notes_off(self) -> None:
        if not self._running:
            return
        try:
            self._cmd_queue.put_nowait(AudioCommand(cmd=EngineCommand.ALL_NOTES_OFF))
        except queue.Full:
            pass

    def set_instrument(self, program: int, channel: int = 0) -> None:
        if not self._running:
            return
        try:
            self._cmd_queue.put_nowait(AudioCommand(cmd=EngineCommand.SET_INSTRUMENT, program=program, channel=channel))
        except queue.Full:
            pass

    def set_volume(self, volume: int) -> None:
        if not self._running:
            return
        try:
            self._cmd_queue.put_nowait(AudioCommand(cmd=EngineCommand.SET_VOLUME, volume=volume))
        except queue.Full:
            pass

    def _enqueue_note_off(self, note: int, channel: int) -> None:
        try:
            self._cmd_queue.put_nowait(AudioCommand(cmd=EngineCommand.NOTE_OFF, note=note, channel=channel))
        except queue.Full:
            pass

    def _driver_order(self) -> list[str]:
        preferred = self._audio_driver if self._audio_driver != "auto" else "pipewire"
        order = [preferred, "pipewire", "pulseaudio", "alsa", "jack", "sdl2", "oss"]
        seen: set[str] = set()
        result: list[str] = []
        for driver in order:
            if driver not in seen:
                seen.add(driver)
                result.append(driver)
        return result

    def _worker(self) -> None:
        try:
            import fluidsynth as fs_lib
        except ImportError:
            self._error = "pyfluidsynth is not installed."
            self._ready.set()
            return

        if not self._soundfont_path:
            self._error = "No SoundFont path configured."
            self._ready.set()
            return

        settings = {
            "audio.sample-rate": self._sample_rate,
            "audio.period-size": self._buffer_size,
            "audio.periods": 2,
            "synth.gain": 2.5,
            "synth.reverb.active": "yes" if self._reverb else "no",
            "synth.chorus.active": "yes" if self._chorus else "no",
            "synth.midi-channels": 16,
            "synth.polyphony": 64,
        }

        started = False
        last_error: Optional[Exception] = None
        for driver in self._driver_order():
            try:
                candidate = fs_lib.Synth(**{**settings, "audio.driver": driver})
                candidate.start(driver=driver)
                self._fs = candidate
                started = True
                logger.info("FluidSynth started with driver: %s", driver)
                break
            except (OSError, RuntimeError, ValueError) as exc:
                last_error = exc
                logger.warning("Audio driver '%s' failed: %s", driver, exc)

        if not started or self._fs is None:
            self._error = f"Cannot start any audio driver: {last_error}"
            self._ready.set()
            return

        try:
            self._sfid = self._fs.sfload(self._soundfont_path)
            if self._sfid == -1:
                raise RuntimeError(f"sfload returned -1 for {self._soundfont_path}")
            for ch in range(16):
                self._fs.sfont_select(ch, self._sfid)
                self._fs.program_change(ch, 0)
            logger.info("SoundFont loaded: %s", self._soundfont_path)
        except (OSError, RuntimeError, ValueError) as exc:
            self._error = f"Failed to load SoundFont: {exc}"
            try:
                self._fs.delete()
            except (OSError, RuntimeError, ValueError):
                pass
            self._ready.set()
            return

        self._ready.set()
        logger.info("FluidSynth backend ready.")

        master_volume = 150
        while True:
            try:
                cmd_obj: AudioCommand = self._cmd_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if cmd_obj.cmd == EngineCommand.SHUTDOWN:
                self._fs.all_notes_off(-1)
                time.sleep(0.05)
                self._fs.delete()
                return

            if cmd_obj.cmd == EngineCommand.NOTE_ON:
                ch = cmd_obj.channel
                note = cmd_obj.note
                vel = int(cmd_obj.velocity * master_volume / 100)
                vel = max(1, min(127, vel))
                active = self._active_notes.setdefault(ch, set())
                if note in active:
                    self._fs.noteoff(ch, note)
                active.add(note)
                self._fs.noteon(ch, note, vel)
            elif cmd_obj.cmd == EngineCommand.NOTE_OFF:
                ch = cmd_obj.channel
                note = cmd_obj.note
                self._fs.noteoff(ch, note)
                self._active_notes.setdefault(ch, set()).discard(note)
            elif cmd_obj.cmd == EngineCommand.ALL_NOTES_OFF:
                self._fs.all_notes_off(-1)
                self._active_notes.clear()
            elif cmd_obj.cmd == EngineCommand.SET_INSTRUMENT:
                ch = cmd_obj.channel
                prog = max(0, min(127, cmd_obj.program))
                self._fs.program_change(ch, prog)
            elif cmd_obj.cmd == EngineCommand.SET_VOLUME:
                master_volume = max(0, min(127, cmd_obj.volume))


class AudioEngine:
    """Runtime audio manager with FluidSynth primary and silent fallback."""

    def __init__(
        self,
        soundfont_path: str,
        audio_driver: str = "auto",
        sample_rate: int = 44100,
        buffer_size: int = 64,
        reverb: bool = True,
        chorus: bool = False,
    ) -> None:
        self._soundfont_path = soundfont_path
        self._audio_driver = audio_driver
        self._sample_rate = sample_rate
        self._buffer_size = buffer_size
        self._reverb = reverb
        self._chorus = chorus
        self._backend: Optional[_BaseAudioBackend] = None
        self._running = False
        self._warning = ""

    def start(self) -> bool:
        if self._running:
            return True

        soundfont_path = self._soundfont_path
        if not soundfont_path:
            try:
                from .config import find_soundfont
            except ImportError:
                find_soundfont = None
            if find_soundfont is not None:
                soundfont_path = find_soundfont() or ""

        if soundfont_path:
            backend = FluidSynthAudioBackend(
                soundfont_path=soundfont_path,
                audio_driver=self._audio_driver,
                sample_rate=self._sample_rate,
                buffer_size=self._buffer_size,
                reverb=self._reverb,
                chorus=self._chorus,
            )
            if backend.start():
                self._backend = backend
                self._running = True
                self._warning = backend.warning
                return True

            self._warning = backend.error or "FluidSynth unavailable. Falling back to silent mode."
            logger.warning(self._warning)

        self._backend = SilentAudioBackend(self._warning or "Audio unavailable. Running in silent mode.")
        self._backend.start()
        self._running = True
        self._warning = self._backend.warning
        return True

    def stop(self) -> None:
        if self._backend:
            self._backend.stop()
        self._running = False

    def play_note(self, note: int, velocity: int, channel: int = 0, duration_ms: int = 120) -> None:
        if self._backend and self._running:
            self._backend.play_note(note=note, velocity=velocity, channel=channel, duration_ms=duration_ms)

    def all_notes_off(self) -> None:
        if self._backend and self._running:
            self._backend.all_notes_off()

    def set_instrument(self, program: int, channel: int = 0) -> None:
        if self._backend and self._running:
            self._backend.set_instrument(program, channel)

    def set_volume(self, volume: int) -> None:
        if self._backend and self._running:
            self._backend.set_volume(volume)

    @property
    def is_ready(self) -> bool:
        return self._running

    @property
    def mode(self) -> AudioMode:
        if self._backend:
            return self._backend.mode
        return AudioMode.SILENT

    @property
    def warning(self) -> str:
        return self._warning

    @property
    def error(self) -> Optional[str]:
        if hasattr(self._backend, "error"):
            return getattr(self._backend, "error")
        return None
