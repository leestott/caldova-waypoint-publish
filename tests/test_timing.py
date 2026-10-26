import json
from pathlib import Path
import unittest


class SessionTimingTests(unittest.TestCase):
    def test_session_and_nested_demo_are_exactly_fifteen_minutes(self):
        order = json.loads((Path(__file__).resolve().parents[1] / "docs" / "running-order.json").read_text())
        self.assertEqual(order["session_duration_ms"], 900_000)
        self.assertEqual(sum(slide["duration_ms"] for slide in order["slides"]), 900_000)
        self.assertEqual(sum(segment["duration_ms"] for segment in order["demo_segments"]), 480_000)
        self.assertEqual(order["setup_duration_ms"] + order["demo_duration_ms"] + order["wrap_duration_ms"], 900_000)
        self.assertEqual(sum(slide["duration_ms"] for slide in order["slides"][:7]) + 15_000, 300_000)
        self.assertEqual(order["slides"][7]["duration_ms"], 15_000 + order["demo_duration_ms"])
        self.assertEqual(sum(slide["duration_ms"] for slide in order["slides"][8:]), 120_000)
        media = [segment for segment in order["demo_segments"] if "media" in segment]
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["duration_ms"], 78_800)
