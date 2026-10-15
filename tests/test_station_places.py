import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from station_places import PlacesError, apply, dump, dump_stations, load, seen_key, validate  # noqa: E402

PID = "ChIJA-pXq72sQjQRVY0AMCPVELc"


def entry(**kw):
    e = {"pid": PID, "src": "auto", "seen": "康寧|康寧路三段30號"}
    e.update(kw)
    return e


class Validate(unittest.TestCase):
    def test_good_entries(self):
        validate({
            "A": entry(),
            "B": entry(pid=None, src="reviewed"),
            "C": entry(src="reviewed", fix={"lat": 22.76, "lng": 120.23, "cpc": [24.84, 120.92]}),
            "D": entry(far=241857),
        })

    def test_errors_name_the_station(self):
        cases = {
            "pid": entry(pid="not a place id!"),
            "src": entry(src="manual"),
            "seen": entry(seen=5),
            "field": entry(colour="blue"),
            "fix text": entry(fix={"lat": "22.7", "lng": 120.2, "cpc": [24.8, 120.9]}),
            "fix outside": entry(fix={"lat": 35.0, "lng": 139.0, "cpc": [24.8, 120.9]}),
            "far": entry(far="far"),
        }
        for label, bad in cases.items():
            with self.subTest(label), self.assertRaisesRegex(PlacesError, "^S1: "):
                validate({"S1": bad})

    def test_load_reports_json_errors_with_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "places.json"
            p.write_text('{\n  "A": {"pid": null, "src": "auto", "seen": "x"},\n}\n', encoding="utf-8")
            with self.assertRaisesRegex(PlacesError, "line 3"):
                load(p)

    def test_missing_file_is_empty(self):
        self.assertEqual(load(Path("/nonexistent/places.json")), {})

    def test_dump_round_trips_one_line_per_station(self):
        places = {"B": entry(), "A": entry(pid=None, src="reviewed")}
        text = dump(places)
        self.assertEqual(json.loads(text), places)
        self.assertEqual(text.splitlines()[1][:5], '  "A"')
        self.assertEqual(len(text.splitlines()), 4)


class Apply(unittest.TestCase):
    def stations(self):
        return [
            {"id": "A", "name": "康寧", "addr": "康寧路三段30號", "lat": 25.0726, "lng": 121.6084},
            {"id": "B", "name": "南寮漁船站", "addr": "漁港路73號", "lat": 24.84566, "lng": 120.92791},
            {"id": "C", "name": "箔子寮漁船站", "addr": "漁港路368號", "lat": 23.6, "lng": 120.1},
            {"id": "N", "name": "新站", "addr": "新路1號", "lat": 23.0, "lng": 120.0},
        ]

    def test_adds_pid_and_fixes(self):
        st = self.stations()
        moved = apply(st, {
            "A": entry(),
            "B": entry(src="reviewed", fix={"lat": 22.764367, "lng": 120.2372958, "cpc": [24.84566, 120.92791]}),
            "C": entry(pid=None, src="reviewed"),
            "GONE": entry(),  # station no longer in CPC's feed: ignored, kept in the file
        })
        self.assertEqual(moved, [])
        self.assertEqual(st[0]["pid"], PID)
        self.assertEqual((st[1]["lat"], st[1]["lng"]), (22.76437, 120.2373))
        self.assertNotIn("pid", st[2])
        self.assertNotIn("pid", st[3])

    def test_reports_cpc_moving_a_fixed_pin(self):
        st = self.stations()
        moved = apply(st, {"B": entry(src="reviewed", fix={"lat": 22.76, "lng": 120.23, "cpc": [24.80, 120.92791]})})
        self.assertEqual(moved, [{"id": "B", "cpc": [24.84566, 120.92791]}])
        self.assertEqual(st[1]["lat"], 22.76)  # the owner's fix still wins

    def test_seen_key(self):
        self.assertEqual(seen_key(self.stations()[0]), "康寧|康寧路三段30號")

    def test_dump_stations_is_compact(self):
        self.assertEqual(dump_stations({"a": [1, "台"]}), '{"a":[1,"台"]}')


if __name__ == "__main__":
    unittest.main()
