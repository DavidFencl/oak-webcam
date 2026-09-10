import os
import unittest
from unittest.mock import patch

from main import validate_frame
from presets.attention_state import FacingTimer
from presets.config import PRESETS, selected


class PresetTests(unittest.TestCase):
    def test_unknown_preset_fails_before_startup(self):
        with patch.dict(os.environ, OAK_WEBCAM_PRESET="typo"):
            with self.assertRaisesRegex(ValueError, "Unknown OAK_WEBCAM_PRESET"):
                selected()

    def test_frame_contract_follows_preset(self):
        class Frame:
            def getWidth(self): return 1920
            def getHeight(self): return 1080
            def getType(self): return "NV12"

        validate_frame(Frame(), "NV12", PRESETS["rgb-1080p"])
        with self.assertRaisesRegex(ValueError, "3840x2160"):
            validate_frame(Frame(), "NV12", PRESETS["rgb-4k"])

    def test_timer_resets_for_away_missing_and_stale_frames(self):
        timer = FacingTimer()
        self.assertEqual(timer.update(0, 0, 0), (True, 0))
        self.assertEqual(timer.update(0.25, 0, 0), (True, 0.25))
        self.assertEqual(timer.update(0.5, 35, 0), (False, 0))
        self.assertEqual(timer.update(0.75, 0, 0), (True, 0))
        self.assertEqual(timer.update(1), (False, 0))
        self.assertEqual(timer.update(1.25, 0, 0), (True, 0))
        self.assertEqual(timer.update(3, 0, 0), (True, 0))
        self.assertEqual(timer.update(3.25, float("nan"), 0), (False, 0))

    def test_timer_does_not_carry_across_face_jump(self):
        timer = FacingTimer()
        a, b = (0.1, 0.1, 0.3, 0.3), (0.6, 0.6, 0.8, 0.8)
        timer.update(0, 0, 0, a)
        self.assertEqual(timer.update(0.25, 0, 0, a), (True, 0.25))
        self.assertEqual(timer.update(0.5, 0, 0, b), (True, 0))
