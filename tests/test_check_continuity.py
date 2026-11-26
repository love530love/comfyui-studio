import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "short-drama-pipeline" / "scripts" / "check_continuity.py"

try:
    from PIL import Image
except ImportError:
    Image = None


CONTRACTS = {
    "characters": {
        "hero": {
            "anchor": "hero anchor",
            "negative_required": ["changed outfit"],
            "forbidden_positive": ["full-face helmet", "visor", "blood"],
            "states": {"helmet": ["worn", "off"], "held_right": ["none", "bag"]},
        }
    },
    "props": {
        "bag": {"anchor": "ice bag", "forbidden": ["cooler"]},
        "cup": {"anchor": "clear cup", "forbidden": ["soda can"]},
    },
}


def shot(shot_id, duration, **overrides):
    data = {
        "id": shot_id,
        "duration": duration,
        "shot_type": "CU",
        "camera": "fixed",
        "beat": "beat",
        "characters": ["hero"],
        "prompt": "hero anchor; close-up",
        "negative": "changed outfit",
        "seed": 1,
        "keyframe": f"03_keyframes/ep02/{shot_id}.png",
        "video": False,
        "status": "todo",
        "axis_side": "A",
        "transition": {"type": "cut"},
    }
    data.update(overrides)
    return data


def shotlist(shots, **overrides):
    data = {
        "episode": 2,
        "duration_target": sum(float(s["duration"]) for s in shots),
        "video_target": {"min": 0, "max": 99},
        "scenes": [
            {
                "scene": 1,
                "location": "hallway",
                "axis": "A",
                "shots": shots,
            }
        ],
    }
    data.update(overrides)
    return data


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="continuity-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.write_contracts(CONTRACTS)

    def write_contracts(self, data):
        path = self.tmp / "01_series" / "continuity" / "contracts.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def write_shotlist(self, data):
        path = self.tmp / "shotlist" / "ep02.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        return path

    def run_checker(self, data, *args):
        self.write_shotlist(data)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project", str(self.tmp), "--episode", "2", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_valid_episode_passes_strict(self):
        shots = [
            shot("ep02_s001", 2.0, transition={"type": "open"}),
            shot(
                "ep02_s002",
                3.0,
                prompt="hero anchor; ice bag close-up",
                props={"bag": "present"},
                state={"hero": {"held_right": "bag"}},
                transition={"type": "state_change", "motivated_by": "he lifts the bag"},
                acceptance=["bag in right hand"],
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cut_with_state_change_fails(self):
        shots = [
            shot("ep02_s001", 2.0, transition={"type": "open"}),
            shot(
                "ep02_s002",
                3.0,
                state={"hero": {"held_right": "bag"}},
                transition={"type": "cut"},
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("不允许状态变化", result.stdout)

    def test_state_change_without_motivation_fails(self):
        shots = [
            shot("ep02_s001", 2.0, transition={"type": "open"}),
            shot(
                "ep02_s002",
                3.0,
                state={"hero": {"held_right": "bag"}},
                transition={"type": "state_change"},
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("motivated_by", result.stdout)

    def test_axis_flip_fails(self):
        shots = [
            shot("ep02_s001", 2.0, transition={"type": "open"}),
            shot("ep02_s002", 3.0, axis_side="B", transition={"type": "cut"}),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("越轴", result.stdout)

    def test_missing_anchor_fails_strict(self):
        shots = [
            shot("ep02_s001", 2.0, prompt="close-up only", transition={"type": "open"}),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("锚点", result.stdout)

    def test_forbidden_positive_fails_even_without_strict(self):
        shots = [
            shot("ep02_s001", 2.0, prompt="hero anchor; full-face helmet", transition={"type": "open"}),
        ]
        result = self.run_checker(shotlist(shots))
        self.assertEqual(result.returncode, 1)
        self.assertIn("禁用词", result.stdout)

    def test_negated_forbidden_term_passes(self):
        shots = [
            shot(
                "ep02_s001",
                2.0,
                prompt="hero anchor; open-face helmet with no visor and no chin bar, no blood",
                transition={"type": "open"},
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_modal_can_is_not_forbidden(self):
        shots = [
            shot(
                "ep02_s001",
                2.0,
                prompt="hero anchor; he can see the clear cup",
                props={"cup": "present"},
                transition={"type": "open"},
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_soda_can_fails(self):
        shots = [
            shot(
                "ep02_s001",
                2.0,
                prompt="hero anchor; clear cup next to a soda can",
                props={"cup": "present"},
                transition={"type": "open"},
            ),
        ]
        result = self.run_checker(shotlist(shots), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("soda can", result.stdout)

    def test_duration_mismatch_fails(self):
        shots = [shot("ep02_s001", 2.0, transition={"type": "open"})]
        result = self.run_checker(shotlist(shots, duration_target=3.0), "--strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("时长不闭合", result.stdout)

    @unittest.skipIf(Image is None, "Pillow not installed")
    def test_contact_sheet_generated(self):
        shots = [shot("ep02_s001", 2.0, transition={"type": "open"})]
        keyframe = self.tmp / "03_keyframes" / "ep02" / "ep02_s001.png"
        keyframe.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (320, 480), (32, 64, 96)).save(keyframe)
        sheet = self.tmp / "09_logs" / "contact" / "ep02_keyframes.png"
        result = self.run_checker(shotlist(shots), "--strict", "--sheet", str(sheet))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(sheet.is_file())


if __name__ == "__main__":
    unittest.main()
