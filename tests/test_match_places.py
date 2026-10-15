import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from match_places import far_unfixed, reviewed_changes, run, todo  # noqa: E402
from station_places import seen_key  # noqa: E402


def station(sid, name="測試站", addr="中正路1號", lat=25.04, lng=121.51):
    return {"id": sid, "name": name, "city": "台北市", "district": "中正區", "addr": addr, "lat": lat, "lng": lng}


def listing(pid, name="台灣中油 測試站", lat=25.04, lng=121.51, addr="100臺北市中正區中正路1號"):
    return {"id": pid, "displayName": {"text": name}, "location": {"latitude": lat, "longitude": lng},
            "formattedAddress": addr, "businessStatus": "OPERATIONAL"}


def google(results):
    """Fake search: results maps a station name to its listings; counts calls."""
    calls = []

    def search(body):
        calls.append(body["textQuery"])
        for name, found in results.items():
            if name in body["textQuery"]:
                return found
        return []
    search.calls = calls
    return search


PID = "ChIJA-pXq72sQjQRVY0AMCPVELc"


class Todo(unittest.TestCase):
    def test_new_and_changed_auto_only(self):
        a, b, c = station("A"), station("B", addr="新地址9號"), station("C", addr="新地址9號")
        places = {
            "B": {"pid": PID, "src": "auto", "seen": "測試站|中正路1號"},      # changed → redo
            "C": {"pid": PID, "src": "reviewed", "seen": "測試站|中正路1號"},  # reviewed → never
        }
        self.assertEqual([s["id"] for s in todo([a, b, c], places)], ["A", "B"])
        self.assertEqual(reviewed_changes([a, b, c], places), ["C"])


class Run(unittest.TestCase):
    def test_new_station_matched_and_saved(self):
        s = station("A")
        places = {}
        report = run([s], places, google({"測試站": [listing(PID)]}))
        self.assertEqual(report["matched"], ["A"])
        self.assertEqual(places["A"], {"pid": PID, "src": "auto", "seen": seen_key(s)})
        self.assertEqual(s["pid"], PID)

    def test_changed_station_no_longer_matching_loses_its_old_match(self):
        s = station("A", addr="新地址9號")
        s["pid"] = PID
        places = {"A": {"pid": PID, "src": "auto", "seen": "測試站|中正路1號"}}
        report = run([s], places, google({}))
        self.assertEqual(report["doubtful"], [{"id": "A", "pid": None, "verdict": "none"}])
        self.assertNotIn("A", places)
        self.assertNotIn("pid", s)

    def test_far_match_is_saved_and_listed_until_fixed(self):
        s = station("A", name="南寮漁船站", addr="彌陀區南寮里漁港路73號", lat=24.84566, lng=120.92791)
        far = listing(PID, "台灣中油 南寮站(直營站附漁船加油)", 22.764367, 120.237296, "827高雄市彌陀區南寮里漁港路73號")
        places = {}
        report = run([s], places, google({"漁港路73號": [far]}))  # only the address search finds it
        self.assertEqual(report["far"], ["A"])
        self.assertGreater(places["A"]["far"], 200_000)
        self.assertEqual(far_unfixed([s], places), [{"id": "A", "pid": PID, "far": places["A"]["far"]}])
        places["A"]["fix"] = {"lat": 22.76, "lng": 120.23, "cpc": [24.84566, 120.92791]}
        self.assertEqual(far_unfixed([s], places), [])

    def test_limit_per_run(self):
        stations = [station(c) for c in "ABC"]
        report = run(stations, {}, google({"測試站": [listing(PID)]}), limit=2)
        self.assertEqual(report["matched"], ["A", "B"])
        self.assertEqual(report["remaining"], 1)

    def test_google_error_keeps_earlier_matches_and_stops(self):
        stations = [station("A"), station("B"), station("C")]
        calls = []

        def search(body):
            calls.append(1)
            if len(calls) > 1:
                raise urllib.error.HTTPError("https://places.googleapis.com", 403, "Forbidden", None, None)
            return [listing(PID)]
        places = {}
        report = run(stations, places, search)
        self.assertEqual(report["matched"], ["A"])
        self.assertIn("403", report["error"])
        self.assertEqual(report["remaining"], 2)
        self.assertEqual(list(places), ["A"])


if __name__ == "__main__":
    unittest.main()
