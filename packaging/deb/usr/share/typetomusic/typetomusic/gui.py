"""
GUI Layer for TypeToMusic.
Built with PyQt5. Dark, instrument-panel aesthetic.
All interaction with the controller is via method calls and Qt signals.
"""

import logging
import math
import time
from collections import deque
from typing import TYPE_CHECKING

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox, QFrame, QFileDialog,
    QSizePolicy, QGroupBox,
)
from PyQt5.QtCore import (
    Qt, QTimer, pyqtSlot, QPropertyAnimation, QEasingCurve,
    QRectF, QPointF,
)
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QFontDatabase,
)

from .config import AppConfig, GM_INSTRUMENTS, SCALES, NOTE_NAMES

if TYPE_CHECKING:
    from .app import AppController

logger = logging.getLogger(__name__)

# ── Colour Palette ─────────────────────────────────────────────────────────────

C_BG        = QColor("#0d0d12")
C_PANEL     = QColor("#14141e")
C_SURFACE   = QColor("#1c1c2a")
C_BORDER    = QColor("#2a2a3d")
C_ACCENT    = QColor("#6c63ff")
C_ACCENT2   = QColor("#ff6584")
C_GREEN     = QColor("#4cefb3")
C_YELLOW    = QColor("#ffd166")
C_TEXT      = QColor("#e8e8f0")
C_MUTED     = QColor("#5c5c7a")

STYLESHEET = """
QWidget {
    background: transparent;
    color: #e8e8f0;
    font-family: 'IBM Plex Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 12px;
}

QGroupBox {
    border: 1px solid #2a2a3d;
    border-radius: 8px;
    margin-top: 16px;
    padding: 6px 4px 4px 4px;
    background: #14141e;
    font-size: 10px;
    color: #5c5c7a;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QComboBox {
    background: #1c1c2a;
    border: 1px solid #2a2a3d;
    border-radius: 5px;
    padding: 5px 8px;
    color: #e8e8f0;
    min-height: 28px;
}
QComboBox:hover { border-color: #6c63ff; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6c63ff;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #1c1c2a;
    border: 1px solid #2a2a3d;
    selection-background-color: #6c63ff;
    color: #e8e8f0;
    outline: none;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a3d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #6c63ff;
    border: none;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal {
    background: #6c63ff;
    border-radius: 2px;
}
QSlider::handle:horizontal:hover { background: #8b84ff; }

QCheckBox {
    spacing: 8px;
    color: #e8e8f0;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #2a2a3d;
    border-radius: 4px;
    background: #1c1c2a;
}
QCheckBox::indicator:checked {
    background: #6c63ff;
    border-color: #6c63ff;
    image: none;
}
QCheckBox::indicator:hover { border-color: #6c63ff; }
"""


# ── Visualiser Widget ──────────────────────────────────────────────────────────

class NoteVisualiser(QWidget):
    """
    Animated waveform/orb that pulses when notes are played.
    Keeps a rolling history of (time, note, velocity) events.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._events: deque = deque(maxlen=32)   # (timestamp, note, vel)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)                     # ~30 fps
        self._phase = 0.0

    def register_note(self, note: int, velocity: int) -> None:
        self._events.append((time.monotonic(), note, velocity))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        now  = time.monotonic()
        self._phase += 0.04

        # Background
        painter.fillRect(0, 0, w, h, C_SURFACE)

        # Draw ripple rings for recent notes
        for ts, note, vel in self._events:
            age = now - ts
            if age > 1.2:
                continue
            progress = age / 1.2        # 0 → 1
            alpha    = int(200 * (1 - progress))
            radius   = int((w * 0.08) + progress * w * 0.42)
            # Map note to hue
            hue      = int((note % 24) / 24 * 300)
            color    = QColor.fromHsv(hue, 200, 255, alpha)
            pen      = QPen(color, max(1, int(3 * (1 - progress))))
            painter.setPen(pen)
            cx = int(w * (0.1 + (note % 12) / 12 * 0.8))
            cy = h // 2
            painter.drawEllipse(QPointF(cx, cy), radius, radius * 0.5)

        # Animated base waveform
        recent = [e for e in self._events if (now - e[0]) < 0.4]
        amplitude = 12.0
        if recent:
            avg_vel = sum(e[2] for e in recent) / len(recent)
            amplitude = 8 + avg_vel / 127 * 22

        pen = QPen(C_ACCENT, 1.5)
        painter.setPen(pen)
        path = QPainterPath()
        steps = 120
        for i in range(steps + 1):
            x   = w * i / steps
            t   = i / steps * math.pi * 6 + self._phase
            y   = h / 2 + amplitude * math.sin(t) * math.cos(self._phase * 0.3)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.drawPath(path)

        # Dim border
        painter.setPen(QPen(C_BORDER, 1))
        painter.drawRect(0, 0, w - 1, h - 1)


# ── Status LED ────────────────────────────────────────────────────────────────

class StatusLED(QWidget):
    """Pulsing coloured LED indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color   = C_MUTED
        self._pulse   = 0.0
        self._pulsing = False
        self._timer   = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_state(self, state: str) -> None:
        """state: 'off' | 'ready' | 'active' | 'error'"""
        states = {
            "off":    (C_MUTED,   False),
            "ready":  (C_YELLOW,  False),
            "active": (C_GREEN,   True),
            "error":  (C_ACCENT2, True),
        }
        color, pulse = states.get(state, (C_MUTED, False))
        self._color   = color
        self._pulsing = pulse
        if pulse and not self._timer.isActive():
            self._timer.start(50)
        elif not pulse:
            self._timer.stop()
            self._pulse = 0.0
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.15) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        alpha = 255
        if self._pulsing:
            alpha = int(180 + 75 * math.sin(self._pulse))
        color = QColor(self._color)
        color.setAlpha(alpha)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 10, 10)

        # Highlight
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawEllipse(3, 2, 4, 3)


# ── Big Toggle Button ─────────────────────────────────────────────────────────

class ToggleButton(QPushButton):
    """Oversized start/stop button with animated border."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self._update_text()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._update_text()
        self.update()

    def _update_text(self):
        self.setText("⏹  STOP PLAYING" if self._active else "▶  START PLAYING")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Fill
        color = QColor("#1f2d1f") if self._active else QColor("#1a1a2e")
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 8, 8)

        # Border
        border_color = C_GREEN if self._active else C_ACCENT
        pen = QPen(border_color, 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 7, 7)

        # Text
        font = QFont("IBM Plex Mono", 13, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(border_color))
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text())


# ── Labelled Row Helper ────────────────────────────────────────────────────────

def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
    lbl = QLabel(label_text)
    lbl.setFixedWidth(80)
    lbl.setStyleSheet("color: #5c5c7a; font-size: 11px;")
    row = QHBoxLayout()
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    """Main GUI panel – wired to AppController."""

    def __init__(self, config: AppConfig, controller: "AppController",
                 parent=None):
        super().__init__(parent)
        self._config     = config
        self._controller = controller
        self._active     = False

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._connect_signals()
        self._populate_combos()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title  = QLabel("TypeToMusic")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; "
            "color: #6c63ff; letter-spacing: 2px;"
        )
        self._led    = StatusLED()
        self._status = QLabel("Initialising…")
        self._status.setStyleSheet("color: #5c5c7a; font-size: 11px;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._led)
        header.addWidget(self._status)
        root.addLayout(header)

        # ── Visualiser ────────────────────────────────────────────────────
        self._vis = NoteVisualiser()
        root.addWidget(self._vis)

        # ── Toggle button ─────────────────────────────────────────────────
        self._toggle_btn = ToggleButton()
        self._toggle_btn.clicked.connect(self._on_toggle)
        root.addWidget(self._toggle_btn)

        # ── Instrument & Scale group ──────────────────────────────────────
        ctrl_grp = QGroupBox("Sound")
        ctrl_layout = QVBoxLayout(ctrl_grp)
        ctrl_layout.setSpacing(8)

        self._instrument_cb = QComboBox()
        ctrl_layout.addLayout(_row("Instrument", self._instrument_cb))

        scale_row = QHBoxLayout()
        self._scale_cb = QComboBox()
        self._scale_cb.setMinimumWidth(130)
        self._root_cb  = QComboBox()
        self._root_cb.setMinimumWidth(60)
        scale_row.addWidget(QLabel("Scale"))
        scale_row.itemAt(0).widget().setFixedWidth(80)
        scale_row.itemAt(0).widget().setStyleSheet("color:#5c5c7a;font-size:11px;")
        scale_row.addWidget(self._scale_cb)
        scale_row.addSpacing(8)
        scale_row.addWidget(QLabel("Root"))
        scale_row.itemAt(3).widget().setStyleSheet("color:#5c5c7a;font-size:11px;")
        scale_row.addWidget(self._root_cb)
        ctrl_layout.addLayout(scale_row)

        root.addWidget(ctrl_grp)

        # ── Volume & Options group ────────────────────────────────────────
        opt_grp    = QGroupBox("Controls")
        opt_layout = QVBoxLayout(opt_grp)
        opt_layout.setSpacing(8)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 127)
        self._volume_slider.setValue(self._config.volume)
        self._volume_lbl    = QLabel(str(self._config.volume))
        self._volume_lbl.setFixedWidth(28)
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Volume"))
        vol_row.itemAt(0).widget().setFixedWidth(80)
        vol_row.itemAt(0).widget().setStyleSheet("color:#5c5c7a;font-size:11px;")
        vol_row.addWidget(self._volume_slider)
        vol_row.addWidget(self._volume_lbl)
        opt_layout.addLayout(vol_row)

        self._speed_vel_cb = QCheckBox("Typing speed → note velocity")
        self._speed_vel_cb.setChecked(self._config.velocity_from_speed)
        opt_layout.addWidget(self._speed_vel_cb)

        root.addWidget(opt_grp)

        # ── SoundFont path ────────────────────────────────────────────────
        sf_grp    = QGroupBox("SoundFont")
        sf_layout = QHBoxLayout(sf_grp)
        self._sf_label = QLabel(
            self._config.soundfont_path or "No SoundFont selected"
        )
        self._sf_label.setStyleSheet("color: #5c5c7a; font-size: 10px;")
        self._sf_label.setWordWrap(True)
        sf_btn = QPushButton("Browse…")
        sf_btn.setFixedWidth(70)
        sf_btn.setStyleSheet(
            "QPushButton{background:#1c1c2a;border:1px solid #2a2a3d;"
            "border-radius:4px;padding:4px 8px;color:#e8e8f0;}"
            "QPushButton:hover{border-color:#6c63ff;}"
        )
        sf_btn.clicked.connect(self._on_browse_sf)
        sf_layout.addWidget(self._sf_label)
        sf_layout.addWidget(sf_btn)
        root.addWidget(sf_grp)

        # ── Note info bar ─────────────────────────────────────────────────
        self._note_lbl = QLabel("—")
        self._note_lbl.setAlignment(Qt.AlignCenter)
        self._note_lbl.setStyleSheet(
            "color: #6c63ff; font-size: 14px; font-weight: bold; "
            "background: #14141e; border: 1px solid #2a2a3d; "
            "border-radius: 5px; padding: 4px;"
        )
        root.addWidget(self._note_lbl)

        root.addStretch()

    # ── Populate combos ───────────────────────────────────────────────────

    def _populate_combos(self):
        # Instruments
        for prog, name in GM_INSTRUMENTS:
            self._instrument_cb.addItem(name, prog)
        # Select current
        for i in range(self._instrument_cb.count()):
            if self._instrument_cb.itemData(i) == self._config.instrument_program:
                self._instrument_cb.setCurrentIndex(i)
                break

        # Scales
        scale_display = {
            "major": "Major", "minor": "Minor", "pentatonic": "Pentatonic",
            "chromatic": "Chromatic", "blues": "Blues", "dorian": "Dorian",
            "lydian": "Lydian", "mixolydian": "Mixolydian",
            "whole_tone": "Whole Tone", "harmonic_minor": "Harmonic Minor",
        }
        for key, label in scale_display.items():
            self._scale_cb.addItem(label, key)
        idx = list(scale_display.keys()).index(self._config.scale) \
              if self._config.scale in scale_display else 0
        self._scale_cb.setCurrentIndex(idx)

        # Root notes
        for i, name in enumerate(NOTE_NAMES):
            self._root_cb.addItem(f"{name}", i)
        self._root_cb.setCurrentIndex(self._config.root_note % 12)

    # ── Signal wiring ─────────────────────────────────────────────────────

    def _connect_signals(self):
        # Controller → GUI
        self._controller.status_changed.connect(self._on_status)
        self._controller.note_played.connect(self._on_note_played)
        self._controller.engine_ready.connect(self._on_engine_ready)

        # GUI widgets → controller
        self._instrument_cb.currentIndexChanged.connect(self._on_instrument_change)
        self._scale_cb.currentIndexChanged.connect(self._on_scale_change)
        self._root_cb.currentIndexChanged.connect(self._on_root_change)
        self._volume_slider.valueChanged.connect(self._on_volume_change)
        self._speed_vel_cb.toggled.connect(self._controller.set_velocity_from_speed)

    # ── Slots ─────────────────────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_status(self, message: str, level: str) -> None:
        self._status.setText(message)
        colors = {"ok": "#4cefb3", "warn": "#ffd166", "error": "#ff6584"}
        self._status.setStyleSheet(
            f"color: {colors.get(level, '#5c5c7a')}; font-size: 11px;"
        )
        led_states = {"ok": "ready", "warn": "ready", "error": "error"}
        self._led.set_state(led_states.get(level, "off"))

    @pyqtSlot(bool)
    def _on_engine_ready(self, ready: bool) -> None:
        self._toggle_btn.setEnabled(ready)
        if ready:
            self._led.set_state("ready")
        else:
            self._led.set_state("error")

    @pyqtSlot(int, int)
    def _on_note_played(self, note: int, velocity: int) -> None:
        self._vis.register_note(note, velocity)
        octave   = note // 12 - 1
        name     = NOTE_NAMES[note % 12]
        self._note_lbl.setText(f"♪  {name}{octave}   vel={velocity}")

    def _on_toggle(self):
        if self._active:
            self._controller.stop_listening()
            self._active = False
            self._toggle_btn.set_active(False)
            self._led.set_state("ready")
            self._note_lbl.setText("—")
        else:
            ok = self._controller.start_listening()
            if ok:
                self._active = True
                self._toggle_btn.set_active(True)
                self._led.set_state("active")

    def _on_instrument_change(self, _idx: int) -> None:
        prog = self._instrument_cb.currentData()
        if prog is not None:
            self._controller.set_instrument(prog)

    def _on_scale_change(self, _idx: int) -> None:
        key = self._scale_cb.currentData()
        if key:
            self._controller.set_scale(key)

    def _on_root_change(self, idx: int) -> None:
        # Map 0–11 to MIDI 48 (C3) + interval
        midi_root = 48 + idx
        self._controller.set_root_note(midi_root)

    def _on_volume_change(self, value: int) -> None:
        self._volume_lbl.setText(str(value))
        self._controller.set_volume(value)

    def _on_browse_sf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SoundFont", "",
            "SoundFont files (*.sf2 *.sf3);;All files (*)"
        )
        if path:
            self._sf_label.setText(path)
            self._controller.set_soundfont(path)

    # ── Background paint ──────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), C_BG)
