"""
Tests for TypeToMusic core modules.
Run with: python -m pytest tests/ -v
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Config tests ─────────────────────────────────────────────────────────────

class TestAppConfig:
    def test_defaults(self):
        from typetomusic.config import AppConfig
        cfg = AppConfig()
        assert cfg.scale == "major"
        assert 0 <= cfg.volume <= 127
        assert cfg.octave_range >= 1

    def test_save_load_roundtrip(self, tmp_path, monkeypatch):
        from typetomusic import config as cfg_mod
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE",
                            str(tmp_path / "config.json"))
        from typetomusic.config import AppConfig
        c = AppConfig()
        c.volume = 77
        c.scale  = "blues"
        c.save()
        c2 = AppConfig.load()
        assert c2.volume == 77
        assert c2.scale  == "blues"


# ── Scale mapper tests ────────────────────────────────────────────────────────

class TestScaleMapper:
    def test_major_scale_notes(self):
        from typetomusic.scale_mapper import ScaleMapper, build_note_sequence
        notes = build_note_sequence("major", 60, 1)
        # C major from C4: C D E F G A B
        assert notes == [60, 62, 64, 65, 67, 69, 71]

    def test_pentatonic(self):
        from typetomusic.scale_mapper import build_note_sequence
        notes = build_note_sequence("pentatonic", 60, 1)
        assert len(notes) == 5

    def test_note_for_index_wraps(self):
        from typetomusic.scale_mapper import ScaleMapper
        mapper = ScaleMapper("major", 60, 1)
        n = mapper.note_count
        # Index n should be the first note of the next octave
        note_0 = mapper.note_for_index(0)
        note_n = mapper.note_for_index(n)
        assert note_n == note_0 + 12

    def test_note_clamps_to_127(self):
        from typetomusic.scale_mapper import ScaleMapper
        mapper = ScaleMapper("chromatic", 120, 1)
        for i in range(100):
            assert 0 <= mapper.note_for_index(i) <= 127

    def test_update_scale(self):
        from typetomusic.scale_mapper import ScaleMapper
        mapper = ScaleMapper("major", 60, 1)
        mapper.update(scale_name="minor")
        assert mapper.scale_name == "minor"
        # Minor has 7 notes, different intervals
        notes = [mapper.note_for_index(i) for i in range(mapper.note_count)]
        assert 63 in notes   # Eb is in C minor


# ── Velocity tracker tests ────────────────────────────────────────────────────

class TestVelocityTracker:
    def test_single_press_low_velocity(self):
        from typetomusic.keyboard_listener import VelocityTracker
        vt = VelocityTracker(window_ms=500)
        vel = vt.record_keypress()
        assert 1 <= vel <= 127

    def test_rapid_presses_higher_velocity(self):
        import time
        from typetomusic.keyboard_listener import VelocityTracker
        vt = VelocityTracker(window_ms=500)
        first = vt.record_keypress()
        for _ in range(9):
            vt.record_keypress()
        last = vt.record_keypress()
        assert last >= first


# ── Key string normalisation ──────────────────────────────────────────────────

class TestKeyToStr:
    def test_char_key(self):
        from typetomusic.keyboard_listener import _key_to_str
        from unittest.mock import MagicMock
        key = MagicMock()
        key.char = "a"
        assert _key_to_str(key) == "a"

    def test_ignored_special_key(self):
        from typetomusic.keyboard_listener import _key_to_str
        from unittest.mock import MagicMock
        key = MagicMock(spec=[])
        key.name = "ctrl_l"
        assert _key_to_str(key) is None

    def test_space_key(self):
        from typetomusic.keyboard_listener import _key_to_str
        from unittest.mock import MagicMock
        key = MagicMock(spec=[])
        key.name = "space"
        result = _key_to_str(key)
        assert result == "space"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
