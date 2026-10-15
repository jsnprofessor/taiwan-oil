import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from review_issue import build  # noqa: E402

PID = "ChIJA-pXq72sQjQRVY0AMCPVELc"
STATIONS = {"A": {"id": "A", "name": "康寧", "city": "台北市", "district": "內湖區",
                  "addr": "康寧路三段30號", "lat": 25.0726, "lng": 121.6084}}
EMPTY = {"matched": [], "far": [], "doubtful": [], "error": None, "remaining": 0,
         "reviewed_changed": [], "far_unfixed": []}


class Build(unittest.TestCase):
    def test_nothing_to_check(self):
        self.assertEqual(build([], EMPTY, STATIONS), "")

    def test_doubtful_lists_cpc_pin_and_candidate(self):
        text = build([], {**EMPTY, "doubtful": [{"id": "A", "pid": PID, "verdict": "review"}]}, STATIONS)
        self.assertIn("`A` 康寧", text)
        self.assertIn("https://www.google.com/maps?q=25.0726,121.6084", text)
        self.assertIn(f"place_id:{PID}", text)

    def test_far_moved_changed_and_error_sections(self):
        text = build(
            [{"id": "A", "cpc": [25.1, 121.6]}],
            {**EMPTY, "far_unfixed": [{"id": "A", "pid": PID, "far": 2400}],
             "reviewed_changed": ["A"], "error": "HTTPError: HTTP Error 403: Forbidden", "remaining": 7},
            STATIONS)
        self.assertIn("2.4 公里", text)
        self.assertIn("https://www.google.com/maps?q=25.1,121.6", text)  # CPC's new pin
        self.assertIn("src", text)
        self.assertIn("403", text)
        self.assertIn("7 個站點", text)

    def test_station_gone_from_feed(self):
        text = build([], {**EMPTY, "reviewed_changed": ["GONE"]}, STATIONS)
        self.assertIn("`GONE`", text)


if __name__ == "__main__":
    unittest.main()
