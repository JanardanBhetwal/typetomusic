"""
Scale Mapper for TypeToMusic.
Converts an ordered key index into a MIDI note number
based on the selected musical scale and root note.
"""

import logging
from typing import List

from .config import SCALES

logger = logging.getLogger(__name__)


def build_note_sequence(
    scale_name: str,
    root_note: int,
    octave_range: int,
) -> List[int]:
    """
    Build a flat list of MIDI notes across octave_range octaves
    starting from root_note, using the given scale.

    Example: scale=major, root=60 (C4), octave_range=3
    → [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86, 88]
    """
    intervals = SCALES.get(scale_name, SCALES["major"])
    notes: List[int] = []

    for octave in range(octave_range):
        for interval in intervals:
            midi = root_note + (octave * 12) + interval
            if 0 <= midi <= 127:
                notes.append(midi)

    # Deduplicate while preserving order
    seen: set = set()
    unique: List[int] = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            unique.append(n)

    logger.debug(
        f"Built note sequence: scale={scale_name} root={root_note} "
        f"octaves={octave_range} → {len(unique)} notes"
    )
    return unique


class ScaleMapper:
    """
    Maps an integer key index (0, 1, 2, …) to a MIDI note number,
    wrapping across octaves if necessary.

    The mapping wraps: index % len(note_sequence), then bumps an extra
    octave for each full wrap cycle (up to MIDI max of 127).
    """

    def __init__(self, scale_name: str, root_note: int, octave_range: int):
        self._scale_name  = scale_name
        self._root_note   = root_note
        self._octave_range = octave_range
        self._notes: List[int] = []
        self._rebuild()

    # ── Public API ────────────────────────────────────────────────────────

    def update(
        self,
        scale_name: str | None = None,
        root_note: int | None = None,
        octave_range: int | None = None,
    ) -> None:
        """Update mapper parameters and rebuild the note sequence."""
        if scale_name   is not None: self._scale_name   = scale_name
        if root_note    is not None: self._root_note    = root_note
        if octave_range is not None: self._octave_range = octave_range
        self._rebuild()

    def note_for_index(self, index: int) -> int:
        """
        Return the MIDI note for the given key index.
        Wraps cyclically and shifts up by octave on each full cycle.
        """
        if not self._notes:
            return 60  # C4 fallback

        n     = len(self._notes)
        cycle = index // n
        pos   = index % n
        note  = self._notes[pos] + (cycle * 12)
        return max(0, min(127, note))

    @property
    def scale_name(self) -> str:
        return self._scale_name

    @property
    def root_note(self) -> int:
        return self._root_note

    @property
    def note_count(self) -> int:
        return len(self._notes)

    # ── Internal ──────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        self._notes = build_note_sequence(
            self._scale_name, self._root_note, self._octave_range
        )
