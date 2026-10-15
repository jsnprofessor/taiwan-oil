"""Weekly step: match new or changed stations to their Google Maps listings.

Never fails the job. Problems go to .review/match.json for the review issue.
Only place IDs are stored (Google allows that); see data/places.json.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from place_match import FAR, FIELDS, MATCH, match_station  # noqa: E402
from station_places import PLACES_PATH, PlacesError, dump, dump_stations, load, seen_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIONS_PATH = ROOT / "site" / "data" / "stations.json"
REVIEW_DIR = ROOT / ".review"
MAX_PER_RUN = 50  # keeps a mass renumbering at CPC inside the free search tier
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


def google_search(body, api_key):
    req = urllib.request.Request(
        SEARCH_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELDS})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("places", [])


def todo(stations, places):
    """Stations with no entry, and automatic matches whose CPC name or address changed."""
    out = []
    for s in stations:
        e = places.get(s["id"])
        if e is None or (e["src"] == "auto" and e["seen"] != seen_key(s)):
            out.append(s)
    return out


def run(stations, places, search, limit=MAX_PER_RUN):
    """Match up to `limit` stations; updates `places` and each station's pid in place."""
    report = {"matched": [], "far": [], "doubtful": [], "error": None, "remaining": 0}
    items = todo(stations, places)
    done = 0
    for s in items[:limit]:
        try:
            c = match_station(s, search)
        except Exception as e:  # bad key, quota, network: keep what we have, try again next week
            report["error"] = f"{type(e).__name__}: {e}"
            break
        done += 1
        sid = s["id"]
        old = places.get(sid) or {}
        if c and c["verdict"] in (MATCH, FAR):
            entry = {"pid": c["pid"], "src": "auto", "seen": seen_key(s)}
            if "fix" in old:
                entry["fix"] = old["fix"]  # the owner's hand-entered coordinates survive a re-match
            elif c["verdict"] == FAR:
                entry["far"] = c["dist"]
            places[sid] = entry
            s["pid"] = c["pid"]
            report["far" if c["verdict"] == FAR else "matched"].append(sid)
        else:
            if "fix" in old:
                # Keep the owner's fix. Old `seen` stays, so an auto entry is retried weekly and stays in the issue.
                places[sid] = {**old, "pid": None}
            else:
                places.pop(sid, None)  # an old automatic match for a changed station is no longer trusted
            s.pop("pid", None)
            report["doubtful"].append({"id": sid, "pid": c["pid"] if c else None,
                                       "verdict": c["verdict"] if c else "none"})
    report["remaining"] = len(items) - done
    return report


def reviewed_changes(stations, places):
    return [s["id"] for s in stations
            if (e := places.get(s["id"])) and e["src"] == "reviewed" and e["seen"] != seen_key(s)]


def far_unfixed(stations, places):
    return [{"id": s["id"], "pid": e["pid"], "far": e["far"]} for s in stations
            if (e := places.get(s["id"])) and "far" in e and "fix" not in e]


def main():
    data = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    stations = data["stations"]
    try:
        places = load()
    except PlacesError as e:
        sys.exit(f"{PLACES_PATH.name}: {e}")
    key = os.environ.get("PLACES_API_KEY", "")
    if key:
        report = run(stations, places, lambda body: google_search(body, key))
    else:
        report = {"matched": [], "far": [], "doubtful": [], "remaining": len(todo(stations, places)),
                  "error": "PLACES_API_KEY is not set; matching skipped"}
    PLACES_PATH.write_text(dump(places), encoding="utf-8")
    STATIONS_PATH.write_text(dump_stations(data), encoding="utf-8")
    report["reviewed_changed"] = reviewed_changes(stations, places)
    report["far_unfixed"] = far_unfixed(stations, places)
    REVIEW_DIR.mkdir(exist_ok=True)
    (REVIEW_DIR / "match.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Matched {len(report['matched'])}, far {len(report['far'])}, doubtful {len(report['doubtful'])}, "
          f"remaining {report['remaining']}" + (f". Warning: {report['error']}" if report["error"] else ""))


if __name__ == "__main__":
    main()
