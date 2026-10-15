import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from update_stations import build, load_places_or_exit  # noqa: E402

PID = "ChIJA-pXq72sQjQRVY0AMCPVELc"


class Build(unittest.TestCase):
    def test_sorted_with_pid_and_fix(self):
        stations = [
            {"id": "B", "name": "南寮漁船站", "addr": "漁港路73號", "lat": 24.84566, "lng": 120.92791},
            {"id": "A", "name": "康寧", "addr": "康寧路三段30號", "lat": 25.0726, "lng": 121.6084},
        ]
        places = {
            "A": {"pid": PID, "src": "auto", "seen": "康寧|康寧路三段30號"},
            "B": {"pid": None, "src": "reviewed", "seen": "x",
                  "fix": {"lat": 22.764367, "lng": 120.237296, "cpc": [24.84566, 120.92791]}},
        }
        data, moved = build(stations, places, "2026-10-19")
        self.assertEqual([s["id"] for s in data["stations"]], ["A", "B"])
        self.assertEqual(data["updated"], "2026-10-19")
        self.assertEqual(data["stations"][0]["pid"], PID)
        self.assertEqual(data["stations"][1]["lat"], 22.76437)
        self.assertEqual(moved, [])


class LoadPlaces(unittest.TestCase):
    def test_malformed_file_stops_the_update(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places.json"
            p.write_text('{"A": {"pid": 5, "src": "auto", "seen": "x"}}', encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                load_places_or_exit(p)
            self.assertIn("A: pid must be", str(cm.exception.code))
            self.assertIn("not updating", str(cm.exception.code))


if __name__ == "__main__":
    unittest.main()
