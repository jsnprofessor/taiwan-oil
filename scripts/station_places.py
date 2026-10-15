"""Owner-reviewed Google place IDs and coordinate fixes, kept in data/places.json."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from place_match import meters  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLACES_PATH = ROOT / "data" / "places.json"
# Box around Taiwan, Penghu, Kinmen and Matsu
LAT_RANGE = (21.5, 26.5)
LNG_RANGE = (118.0, 122.5)
MOVED_M = 100  # CPC moving a fixed pin further than this is reported
_PID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_FIELDS = {"pid", "src", "seen", "fix", "far"}


class PlacesError(ValueError):
    """data/places.json is malformed."""


def in_taiwan(lat, lng):
    return LAT_RANGE[0] < lat < LAT_RANGE[1] and LNG_RANGE[0] < lng < LNG_RANGE[1]


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check(sid, e):
    if not isinstance(e, dict):
        return "entry must be an object"
    if set(e) - _FIELDS:
        return f"unknown field(s) {sorted(set(e) - _FIELDS)}"
    pid = e.get("pid", "missing")
    if not (pid is None or (isinstance(pid, str) and _PID.match(pid))):
        return "pid must be a Google place ID or null"
    if e.get("src") not in ("auto", "reviewed"):
        return 'src must be "auto" or "reviewed"'
    if not isinstance(e.get("seen"), str):
        return "seen must be text"
    if "far" in e and not _number(e["far"]):
        return "far must be a number of metres"
    if "fix" in e:
        f = e["fix"]
        ok = (isinstance(f, dict) and _number(f.get("lat")) and _number(f.get("lng"))
              and isinstance(f.get("cpc"), list) and len(f["cpc"]) == 2
              and all(_number(x) for x in f["cpc"]))
        if not ok:
            return "fix needs numeric lat, lng and cpc [lat, lng]"
        if not in_taiwan(f["lat"], f["lng"]):
            return f"fix {f['lat']}, {f['lng']} is outside Taiwan"
    return None


def validate(places):
    if not isinstance(places, dict):
        raise PlacesError("top level must be an object keyed by station ID")
    for sid, e in places.items():
        problem = _check(sid, e)
        if problem:
            raise PlacesError(f"{sid}: {problem}")


def load(path=PLACES_PATH):
    if not path.exists():
        return {}
    try:
        places = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PlacesError(f"not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}") from None
    validate(places)
    return places


def dump(places):
    """One station per line, sorted by ID, so git diffs stay readable."""
    lines = [f"  {json.dumps(sid)}: {json.dumps(places[sid], ensure_ascii=False, sort_keys=True)}"
             for sid in sorted(places)]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def seen_key(station):
    """CPC's name and address when matched; a change means the match needs checking."""
    return f"{station['name']}|{station.get('addr', '')}"


def apply(stations, places):
    """Add place IDs and owner fixes to stations (in place).

    Returns fixed stations whose CPC pin moved, with CPC's current coordinates.
    Entries for stations not in CPC's feed are ignored (they may come back).
    """
    moved = []
    for s in stations:
        e = places.get(s["id"])
        if not e:
            continue
        if e["pid"]:
            s["pid"] = e["pid"]
        fix = e.get("fix")
        if fix:
            if meters(s["lat"], s["lng"], *fix["cpc"]) > MOVED_M:
                moved.append({"id": s["id"], "cpc": [s["lat"], s["lng"]]})
            s["lat"], s["lng"] = round(fix["lat"], 5), round(fix["lng"], 5)
    return moved


def dump_stations(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
