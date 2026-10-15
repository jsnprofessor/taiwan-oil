"""Match a CPC station to its Google Maps listing. Pure functions; no network.

The rules come from matching every station on 2026-10-15; see
docs/superpowers/specs/2026-10-15-station-photos-design.md.
"""
import math
import re

NEAR_M = 150    # this close, the name or the address agreeing is enough
FAR_M = 1000    # farther than NEAR_M, the address must agree too
MATCH, FAR, REVIEW, NO = "match", "far", "review", "no"
FIELDS = ("places.id,places.displayName,places.location,places.types,"
          "places.formattedAddress,places.businessStatus")

_BRAND = re.compile(r"中油|CPC", re.I)
_WIDE = str.maketrans("０１２３４５６７８９臺", "0123456789台")
_SECTION = {c: str(i) for i, c in enumerate("〇一二三四五六七八九")}
_STREET = re.compile(r"([^\d]+?(?:路|街|大道|道)(?:\d+段)?(?:[\d之-]+巷)?(?:[\d之-]+弄)?[\d之-]+號)")
_NOTE = re.compile(r"[（(]備註.*?[)）]")
_ORDER = {MATCH: 0, FAR: 0, REVIEW: 1, NO: 2}


def meters(a_lat, a_lng, b_lat, b_lng):
    r = 6371000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def norm(addr):
    """Same spelling for both sides: half-width digits, 台, 3段, 86-1."""
    addr = addr.translate(_WIDE)
    addr = re.sub(r"([一二三四五六七八九])段", lambda m: _SECTION[m.group(1)] + "段", addr)
    addr = re.sub(r"(\d)之(\d)", r"\1-\2", addr)
    return re.sub(r"\s", "", addr)


def street(addr):
    """Road and house number, e.g. 康寧路3段30號; "" when the address has no road."""
    tail = re.split(r"[村里鄰]", norm(addr))[-1]
    m = _STREET.search(tail)
    return m.group(1) if m else ""


def base_name(name):
    return name.removesuffix("站")


def name_match(base, google_name):
    """Contained, or at least 60% of the name's character pairs appear in Google's name."""
    if base in google_name:
        return True
    pairs = [base[i:i + 2] for i in range(len(base) - 1)]
    return len(pairs) >= 2 and sum(p in google_name for p in pairs) / len(pairs) >= 0.6


def cpc_address(station):
    """CPC's address without its 備註 notes, with the city in front."""
    addr = _NOTE.sub("", station.get("addr", "")).strip()
    if norm(addr).startswith(norm(station["city"])):
        return addr
    return station["city"] + station.get("district", "") + addr


def _query(text):
    return {"textQuery": text, "includedType": "gas_station", "strictTypeFiltering": True,
            "languageCode": "zh-TW", "regionCode": "TW", "pageSize": 5}


def name_query(station):
    q = _query(f"台灣中油 {base_name(station['name'])}站")
    q["locationBias"] = {"circle": {
        "center": {"latitude": station["lat"], "longitude": station["lng"]}, "radius": NEAR_M}}
    return q


def address_query(station):
    # no location bias: CPC's pin may be in the wrong town
    return _query("台灣中油 " + cpc_address(station))


def judge(station, place, mode):
    loc = place.get("location", {})
    d = meters(station["lat"], station["lng"], loc.get("latitude", 0), loc.get("longitude", 0))
    name = place.get("displayName", {}).get("text", "")
    cpc_street = street(station.get("addr", ""))
    signals = {
        "brand": bool(_BRAND.search(name)),
        "name": name_match(base_name(station["name"]), name),
        "addr": bool(cpc_street) and street(place.get("formattedAddress", "")).endswith(
            cpc_street.split("市")[-1].split("區")[-1]),
    }
    is_open = place.get("businessStatus", "OPERATIONAL") != "CLOSED_PERMANENTLY"
    strong = signals["name"] or signals["addr"]  # brand alone may be a neighbouring CPC station
    addr_plus = signals["addr"] and (signals["name"] or signals["brand"])
    if mode == "address" and addr_plus:
        verdict = FAR if d > FAR_M else MATCH
    elif is_open and ((d <= NEAR_M and strong) or (d <= FAR_M and addr_plus)):
        verdict = MATCH
    elif is_open and d <= FAR_M and strong:
        verdict = REVIEW
    else:
        verdict = NO
    return {"pid": place["id"], "verdict": verdict, "dist": round(d),
            "signals": [k for k, v in signals.items() if v]}


def best(station, places, mode="name"):
    candidates = [judge(station, p, mode) for p in places]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (
        _ORDER[c["verdict"]], -len(c["signals"]), "brand" not in c["signals"], c["dist"]))


def match_station(station, search):
    """Name search first; the address search only when that isn't a confident match.

    `search(body) -> list of Google place dicts`.
    """
    by_name = best(station, search(name_query(station)), "name")
    if by_name and by_name["verdict"] == MATCH:
        return by_name
    by_addr = best(station, search(address_query(station)), "address")
    if by_addr and by_addr["verdict"] in (MATCH, FAR):
        return by_addr
    if by_name and by_name["verdict"] == REVIEW:
        return by_name
    return by_addr or by_name
