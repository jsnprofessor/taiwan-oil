# Station Photos and Corrected Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show swipeable Google place photos in each station card, route 導航 to the station's exact Google listing, and fix 20 wrongly placed pins, with a weekly job that matches new stations automatically.

**Architecture:** A reviewed file `data/places.json` (station ID → Google place ID, owner coordinate fixes) feeds `update_stations.py`, which adds `pid` and fixes to the published `site/data/stations.json`. A new weekly step `match_places.py` matches new or changed stations using the tested name-then-address search and reports anything doubtful to one GitHub issue. In the browser, a new `photos.js` module fetches the photo list fresh when a card opens and loads each image only when swiped to.

**Tech Stack:** Python 3.11 standard library (scripts, `unittest`), plain ES modules (site), Node's built-in test runner, Google Places API (New) Text Search (scripts) and Maps JavaScript API `places` library (browser), GitHub Actions + `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-10-15-station-photos-design.md`

**Changes from the spec, found while planning (both from Google's docs, checked 2026-10-15):**
1. Photo lists are **not** kept in memory between card opens. Google's place-photos page: "Don't cache photo URIs or photos. Ensure you always get photo data from a fresh Place object." The `photos` request is in the free tier, so this costs nothing.
2. The Google credit text is **"Google Maps"**, not 「Google 地圖」. Maps JavaScript API policies: "Don't localize Google Maps into another language"; text must be at least 12 px.
3. Stations matched by address far from CPC's pin keep a `far` field (metres) in `data/places.json`, so the review issue keeps listing them until the owner adds a fix.

## Global Constraints

- Scripts use the Python standard library only and run under `python3 -I` on Python 3.11. Because `-I` drops the script's folder from `sys.path`, each script and test adds `scripts/` to `sys.path` itself.
- Store from Google only place IDs. Never store Google names, addresses, coordinates, photo names or photo URLs in the repo, in `data/places.json`, or in the public review issue.
- Matching rules, unchanged from testing: MATCH within 150 m when name or address agrees; or within 1,000 m when the address agrees and the name or CPC brand agrees. In the address search, address plus (name or brand) is a match at any distance, flagged `far` when over 1,000 m. REVIEW within 1,000 m when name or address agrees. Names agree if contained, or if at least 60% of the name's character pairs appear. Ties: more signals, then CPC brand, then distance. Listings marked `CLOSED_PERMANENTLY` are not matched by the name search.
- At most 50 stations matched per weekly run.
- A fixed station's CPC pin counts as moved when it is more than 100 m from `fix.cpc`.
- Matching must never fail the weekly job; a malformed `data/places.json` must stop the data update (old data stays live).
- UI strings, exactly: 「相片：{author}」, "Google Maps", 「在 Google 地圖查看更多相片」, 「暫無相片」, 「相片暫時無法顯示」, aria-label 「加油站相片」. Review issue title: 「需要檢查的加油站」.
- Photo images are requested at `maxWidth: 800`, only for the slide that is on screen.
- New site modules are imported with `?v=__BUILD__` (the deploy replaces it in `index.html` and `app.js`).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push until the owner says so (Task 10).

## Review Focus

1. **Owner hand-edits `data/places.json` with a mistake** (trailing comma, text instead of a number, unknown field): the update stops with a message naming the station ID, and the live site keeps its old data. Tested in Task 2.
2. **Google rejects the key mid-run** (403 or quota 429 after some stations): matches made before the error are saved, the rest are counted as remaining, the job continues and the issue says why. Tested in Task 5.
3. **Two station cards opened quickly**: the second card shows only its own photos; the first card's late reply is ignored. Checked in Task 9.
4. **Daily photo cap reached in the evening** (photo image requests answer 429): the slide shows 「相片暫時無法顯示」, never a broken-image icon, and the rest of the card works. Checked in Task 9.
5. **A station disappears from CPC's feed but stays in `data/places.json`**: its entry is kept (it may come back) and nothing breaks. Tested in Task 2.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/place_match.py` (new) | Pure matching logic: address normalising, name comparison, search request bodies, judging Google results, picking the best. No network. |
| `scripts/station_places.py` (new) | Reading, validating and writing `data/places.json`; applying place IDs and coordinate fixes to stations; shared JSON writer for `stations.json`. |
| `scripts/update_stations.py` (modify) | Downloads CPC data as now; then applies `data/places.json`; writes `.review/moved.json`. |
| `scripts/match_places.py` (new) | Weekly step: finds new/changed stations, calls Google Text Search, updates `data/places.json` and `stations.json`, writes `.review/match.json`. |
| `scripts/review_issue.py` (new) | Turns `.review/*.json` into `.review/issue.md` (empty = nothing to check). |
| `data/places.json` (new, generated once in Task 3) | Reviewed matches and fixes. |
| `site/filters.js` (modify) | Gains `directionsUrl(s)` (testable). |
| `site/photos.js` (new) | Photo strip in the station card. |
| `site/app.js`, `site/style.css` (modify) | Use `directionsUrl` from `filters.js`; add photo section; styles. |
| `.github/workflows/deploy.yml` (modify) | Run tests, match step, commit both data files, review issue step. |
| `tests/test_place_match.py`, `tests/test_station_places.py`, `tests/test_update_stations.py`, `tests/test_match_places.py`, `tests/test_review_issue.py` (new) | Python tests. |
| `tests/filters.test.js` (modify) | `directionsUrl` test. |
| `.gitignore`, `README.md` (modify) | Ignore `.review/`; document the new setup. |

Run all Python tests with: `python3 -I -m unittest discover -s tests -p "test_*.py" -v`
Run JavaScript tests with: `node --test tests/*.test.js`

---

### Task 1: Matching logic (`scripts/place_match.py`)

**Files:**
- Create: `scripts/place_match.py`
- Test: `tests/test_place_match.py`

**Interfaces:**
- Produces: constants `NEAR_M = 150`, `FAR_M = 1000`, `MATCH = "match"`, `FAR = "far"`, `REVIEW = "review"`, `NO = "no"`, `FIELDS` (Text Search field mask string); functions `meters(a_lat, a_lng, b_lat, b_lng) -> float`, `norm(addr: str) -> str`, `street(addr: str) -> str`, `base_name(name: str) -> str`, `name_match(base: str, google_name: str) -> bool`, `cpc_address(station: dict) -> str`, `name_query(station) -> dict`, `address_query(station) -> dict`, `judge(station, place: dict, mode: "name"|"address") -> dict`, `best(station, places: list, mode) -> dict | None`, `match_station(station, search: Callable[[dict], list]) -> dict | None`. A candidate dict is `{"pid": str, "verdict": MATCH|FAR|REVIEW|NO, "dist": int metres, "signals": list of "brand"/"name"/"addr"}`. A station dict has `id, name, city, district (may be missing), addr, lat, lng`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_place_match.py
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from place_match import (  # noqa: E402
    FAR, MATCH, NO, REVIEW, address_query, best, cpc_address, match_station,
    name_match, name_query, norm, street,
)


def offset(lat, lng, north_m):
    """A point north_m metres north of (lat, lng)."""
    return lat + north_m / 111_320, lng


def station(sid, name, city, district, addr, lat, lng):
    return {"id": sid, "name": name, "city": city, "district": district,
            "addr": addr, "lat": lat, "lng": lng}


def place(pid, name, lat, lng, addr, status="OPERATIONAL"):
    return {"id": pid, "displayName": {"text": name},
            "location": {"latitude": lat, "longitude": lng},
            "formattedAddress": addr, "businessStatus": status, "types": ["gas_station"]}


class Normalising(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm("臺北市康寧路三段30號"), "台北市康寧路3段30號")
        self.assertEqual(norm("576巷86之1號"), "576巷86-1號")
        self.assertEqual(norm("１２３ 號"), "123號")

    def test_street(self):
        self.assertEqual(street("豐谷里15鄰中華路二段515號"), "中華路2段515號")
        self.assertEqual(street("114臺北市內湖區葫洲里康寧路三段30號"), "康寧路3段30號")
        self.assertEqual(street("樟樹村8鄰竹圍35-1號"), "")

    def test_name_match(self):
        self.assertTrue(name_match("康寧", "台灣中油康寧站(加盟&自助)"))
        self.assertTrue(name_match("山隆銅鑼", "山隆加油站 銅鑼站(中油/人工/自助)"))
        self.assertTrue(name_match("好市多中壢", "好市多Costco中壢加油站"))
        self.assertFalse(name_match("康寧", "台灣中油(直營)-東湖站"))

    def test_cpc_address(self):
        penghu = station("D5534", "鎖港漁船站", "澎湖縣", "", "馬公市鎖港里293號(備註:星期六日暫停營業)", 0, 0)
        self.assertEqual(cpc_address(penghu), "澎湖縣馬公市鎖港里293號")
        chiayi = station("II6212C65", "忠孝路", "嘉義市", "東區", "嘉義市東區忠孝路808號", 0, 0)
        self.assertEqual(cpc_address(chiayi), "嘉義市東區忠孝路808號")

    def test_queries(self):
        s = station("D5139", "南寮漁船站", "高雄市", "", "彌陀區南寮里漁港路73號", 24.84566, 120.92791)
        q = name_query(s)
        self.assertEqual(q["textQuery"], "台灣中油 南寮漁船站")
        self.assertEqual(q["locationBias"]["circle"]["radius"], 150)
        self.assertEqual(q["includedType"], "gas_station")
        self.assertTrue(q["strictTypeFiltering"])
        a = address_query(s)
        self.assertEqual(a["textQuery"], "台灣中油 高雄市彌陀區南寮里漁港路73號")
        self.assertNotIn("locationBias", a)


class RealCases(unittest.TestCase):
    """Cases met while matching all stations on 2026-10-15."""

    def test_makung_far_but_name_and_address_agree(self):
        s = station("D5531", "馬公漁船站", "澎湖縣", "", "馬公市海安街16號(備註:週六暫停營業)", 23.56821, 119.57076)
        boat = place("boat", "台灣中油馬公漁船加油站", *offset(23.56821, 119.57076, 457), "880澎湖縣馬公市啟明里海安街16號880")
        town = place("town", "台灣中油 馬公加油站", *offset(23.56821, 119.57076, -406), "880澎湖縣馬公市啟明里民福路18號")
        c = best(s, [town, boat], "name")
        self.assertEqual((c["pid"], c["verdict"]), ("boat", MATCH))

    def test_shiliu_cpc_brand_beats_franchise_office(self):
        s = station("II6212B98", "佳得美石榴站", "雲林縣", "斗六市", "榴中里石榴路230號", 23.72719, 120.5891)
        office = place("office", "佳得美股份有限公司石榴分公司", *offset(23.72719, 120.5891, 227), "640雲林縣斗六市榴中里石榴路230號")
        cpc = place("cpc", "台灣中油石榴站（ 加盟）", *offset(23.72719, 120.5891, 226), "640雲林縣斗六市榴中里石榴路230號")
        self.assertEqual(best(s, [office, cpc], "name")["pid"], "cpc")

    def test_zhongsen_cpc_listing_beats_inspection_shop(self):
        s = station("LL6212A45", "中森站", "宜蘭縣", "宜蘭市", "中山路5段501號", 24.77969, 121.75923)
        shop = place("shop", "中森加油站 ｜ 中森汽車檢驗廠", 24.77969, 121.75923, "260宜蘭縣宜蘭市茭白里中山路五段501號")
        cpc = place("cpc", "台灣中油 中森站(加盟)", *offset(24.77969, 121.75923, 11), "260宜蘭縣宜蘭市茭白里中山路五段501號")
        self.assertEqual(best(s, [shop, cpc], "name")["pid"], "cpc")

    def test_donghu_in_xizhi_is_only_review(self):
        s = station("D215W", "東湖站", "台北市", "內湖區", "康寧路三段225號", 25.0675, 121.61194)
        xizhi = place("xizhi", "台灣中油 東湖站(汐止康寧街）", *offset(25.0675, 121.61194, 595), "221新北市汐止區北山里康寧街6號")
        c = match_station(s, lambda body: [xizhi] if "locationBias" in body else [])
        self.assertEqual(c["verdict"], REVIEW)

    def test_jiangjun_neighbouring_cpc_listing_rejected(self):
        s = station("D503T", "將軍漁船站(僅星期一營業)", "台南市", "將軍區", "長沙里126-6號", 23.19, 120.11)
        other = place("other", "台灣中油 將軍站(直營&自助)", *offset(23.19, 120.11, 22), "725臺南市將軍區忠嘉里忠興162之1號")
        self.assertEqual(best(s, [other], "name")["verdict"], NO)

    def test_costco_dash_and_zhi_are_the_same(self):
        s = station("YY6212D25", "好市多中壢站", "桃園市", "中壢區", "民族路六段576巷86-1號", 24.9653, 121.1558)
        p = place("costco", "好市多Costco中壢加油站", *offset(24.9653, 121.1558, 26), "320桃園市中壢區過嶺里民族路六段576巷86之1號")
        c = best(s, [p], "name")
        self.assertEqual(c["verdict"], MATCH)
        self.assertIn("addr", c["signals"])

    def test_shanlong_tongluo_character_pairs(self):
        s = station("GG6212A73", "山隆銅鑼站", "苗栗縣", "銅鑼鄉", "樟樹村8鄰竹圍35-1號", 24.4487, 120.7794)
        p = place("shanlong", "山隆加油站 銅鑼站(中油/人工/自助)", *offset(24.4487, 120.7794, 9), "366苗栗縣銅鑼鄉樟樹村35-1號")
        self.assertEqual(best(s, [p], "name")["verdict"], MATCH)

    def test_suogang_garbled_google_address_is_review(self):
        s = station("D5534", "鎖港漁船站", "澎湖縣", "", "馬公市鎖港里293號(備註:星期六日暫停營業)", 23.53306, 119.60538)
        p = place("suogang", "台灣中油鎖港漁船加油站", *offset(23.53306, 119.60538, 564), "880澎湖縣馬公市鎖港里鎖管里293號")
        self.assertEqual(best(s, [p], "name")["verdict"], REVIEW)

    def test_nanliao_found_by_address_far_from_cpc_pin(self):
        s = station("D5139", "南寮漁船站", "高雄市", "", "彌陀區南寮里漁港路73號", 24.84566, 120.92791)
        hsinchu = place("hsinchu", "台灣中油南寮站（直營）", *offset(24.84566, 120.92791, 20), "300新竹市北區南寮里東大路四段292號")
        kaohsiung = place("kaohsiung", "台灣中油 南寮站(直營站附漁船加油)", 22.764367, 120.237296, "827高雄市彌陀區南寮里漁港路73號")
        c = match_station(s, lambda body: [hsinchu] if "locationBias" in body else [kaohsiung])
        self.assertEqual((c["pid"], c["verdict"]), ("kaohsiung", FAR))
        self.assertGreater(c["dist"], 200_000)

    def test_permanently_closed_listing_not_matched(self):
        s = station("X1", "測試站", "台北市", "中正區", "中正路1號", 25.04, 121.51)
        p = place("closed", "台灣中油 測試站", 25.04, 121.51, "100臺北市中正區中正路1號", status="CLOSED_PERMANENTLY")
        self.assertEqual(best(s, [p], "name")["verdict"], NO)

    def test_no_results(self):
        s = station("X1", "測試站", "台北市", "中正區", "中正路1號", 25.04, 121.51)
        self.assertIsNone(match_station(s, lambda body: []))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I -m unittest discover -s tests -p "test_place_match.py" -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'place_match'`.

- [ ] **Step 3: Write `scripts/place_match.py`**

```python
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
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -I -m unittest discover -s tests -p "test_place_match.py" -v`
Expected: all tests `ok`.

- [ ] **Step 5: Commit**

```bash
git add scripts/place_match.py tests/test_place_match.py
git commit -m "Add station-to-Google-listing matching rules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `data/places.json` handling (`scripts/station_places.py`)

**Files:**
- Create: `scripts/station_places.py`
- Test: `tests/test_station_places.py`

**Interfaces:**
- Consumes: `place_match.meters`.
- Produces: `ROOT: Path`, `PLACES_PATH: Path` (= `ROOT / "data" / "places.json"`), `LAT_RANGE = (21.5, 26.5)`, `LNG_RANGE = (118.0, 122.5)`, `MOVED_M = 100`, `class PlacesError(ValueError)`, `validate(places: dict) -> None`, `load(path: Path = PLACES_PATH) -> dict` (missing file → `{}`), `dump(places: dict) -> str`, `seen_key(station: dict) -> str` (`"{name}|{addr}"`), `apply(stations: list, places: dict) -> list[dict]` (returns `[{"id": str, "cpc": [lat, lng]}]` for fixed stations whose CPC pin moved; mutates stations: adds `pid`, replaces `lat`/`lng` with the fix rounded to 5 decimals), `dump_stations(data: dict) -> str` (compact JSON, same format as today). Entry shape: `{"pid": str|None, "src": "auto"|"reviewed", "seen": str, "fix"?: {"lat": num, "lng": num, "cpc": [num, num]}, "far"?: num}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_station_places.py
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I -m unittest discover -s tests -p "test_station_places.py" -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'station_places'`.

- [ ] **Step 3: Write `scripts/station_places.py`**

```python
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
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `python3 -I -m unittest discover -s tests -p "test_station_places.py" -v`
Expected: all tests `ok`.

- [ ] **Step 5: Commit**

```bash
git add scripts/station_places.py tests/test_station_places.py
git commit -m "Add reading, checking and applying of data/places.json

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Create `data/places.json` from the owner's review

One-off: the seed script lives in `scratch/` (git-ignored) and is not committed; only its output is.

**Files:**
- Create (not committed): `scratch/seed_places.py`
- Create: `data/places.json`

**Interfaces:**
- Consumes: `station_places.dump`, `station_places.validate`, `station_places.seen_key`; `scratch/match-test/results.jsonl` (one JSON object per line: `id`, `verdict` in `MATCH|COORD|REVIEW|no`, `place_id`), `scratch/review/2_review.csv` (columns `station_id`, `Google candidate link`, `your decision (same / different / not on Google)`, `correct Google link (if you find it)`), `scratch/review/1_misplaced_pins.csv` (columns `station_id`, `CPC lat`, `CPC lng`, `correct lat`, `correct lng`).
- Produces: `data/places.json` with one entry per station in `site/data/stations.json`.

- [ ] **Step 1: Write the seed script**

```python
# scratch/seed_places.py — one-off; turns the 2026-10-15 review into data/places.json
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from station_places import PLACES_PATH, dump, seen_key, validate  # noqa: E402

stations = {s["id"]: s for s in json.loads((ROOT / "site/data/stations.json").read_text(encoding="utf-8"))["stations"]}
results = {r["id"]: r for r in map(json.loads, (ROOT / "scratch/match-test/results.jsonl").read_text(encoding="utf-8").splitlines())}
review = {r["station_id"]: r for r in csv.DictReader(open(ROOT / "scratch/review/2_review.csv", encoding="utf-8-sig"))}
pins = {r["station_id"]: r for r in csv.DictReader(open(ROOT / "scratch/review/1_misplaced_pins.csv", encoding="utf-8-sig"))}
DECISION = "your decision (same / different / not on Google)"


def pid_from(link):
    m = re.search(r"place_id:([\w-]+)", link or "")
    return m.group(1) if m else None


places = {}
for sid, s in stations.items():
    r = results[sid]
    if sid in review:
        rv = review[sid]
        decision = rv[DECISION].strip()
        if decision == "same":
            pid = pid_from(rv["Google candidate link"])
        elif decision == "different":
            pid = pid_from(rv["correct Google link (if you find it)"])
        elif decision == "not on Google":
            pid = None
        else:
            sys.exit(f"{sid}: unknown decision {decision!r}")
        e = {"pid": pid, "src": "reviewed", "seen": seen_key(s)}
    elif r["verdict"] == "COORD":
        e = {"pid": r["place_id"], "src": "reviewed", "seen": seen_key(s)}
    elif r["verdict"] == "MATCH":
        e = {"pid": r["place_id"], "src": "auto", "seen": seen_key(s)}
    else:
        sys.exit(f"{sid}: verdict {r['verdict']} without a review row")
    if sid in pins:
        p = pins[sid]
        e["src"] = "reviewed"
        e["fix"] = {"lat": round(float(p["correct lat"]), 6), "lng": round(float(p["correct lng"]), 6),
                    "cpc": [float(p["CPC lat"]), float(p["CPC lng"])]}
    places[sid] = e

validate(places)
PLACES_PATH.parent.mkdir(exist_ok=True)
PLACES_PATH.write_text(dump(places), encoding="utf-8")
print(f"wrote {len(places)} entries to {PLACES_PATH}")
```

- [ ] **Step 2: Run it**

Run: `python3 -I scratch/seed_places.py`
Expected: `wrote 1963 entries to …/data/places.json` (the station count may differ by one or two if CPC's feed changed; any `exit` message means a station has no decision. Stop and ask the owner).

- [ ] **Step 3: Check the counts against the review**

Run:
```bash
python3 -I - <<'EOF'
import json, collections
p = json.load(open("data/places.json", encoding="utf-8"))
print("entries", len(p))
print("with pid", sum(1 for e in p.values() if e["pid"]), "| null", [k for k, e in p.items() if e["pid"] is None])
print("src", dict(collections.Counter(e["src"] for e in p.values())))
print("fixes", sum(1 for e in p.values() if "fix" in e))
EOF
```
Expected: `with pid 1962 | null ['D4332']`, `src {'auto': 1888, 'reviewed': 75}`, `fixes 20`. If they differ, stop and show the owner the difference.

- [ ] **Step 4: Check that no Google content other than IDs is in the file**

Run: `grep -cE '台灣中油|formattedAddress|displayName|latitude' data/places.json || true`
Expected: `0` (the `seen` values are CPC's own names and addresses, which never contain 「台灣中油」).

- [ ] **Step 5: Commit**

```bash
git add data/places.json
git commit -m "Add reviewed Google listings and pin fixes for all stations

1,962 place IDs (1,888 automatic, 75 reviewed), 1 station not on Google,
20 owner-entered coordinate fixes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Apply places in the data update (`scripts/update_stations.py`)

**Files:**
- Modify: `scripts/update_stations.py` (imports; remove its own `LAT_RANGE`/`LNG_RANGE`; new `build()` and `load_places_or_exit()`; `main()`)
- Modify: `.gitignore` (add `.review/`)
- Modify: `site/data/stations.json` (regenerated)
- Test: `tests/test_update_stations.py`

**Interfaces:**
- Consumes: from `station_places`: `LAT_RANGE`, `LNG_RANGE`, `PLACES_PATH`, `PlacesError`, `apply`, `dump_stations`, `load`.
- Produces: `build(stations: list, places: dict, today: str) -> (data: dict, moved: list)`; `load_places_or_exit(path) -> dict` (exits with `"<file>: <problem>; not updating."` on `PlacesError`); `REVIEW_DIR = ROOT / ".review"`; writes `.review/moved.json` (JSON list from `apply`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_update_stations.py
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I -m unittest discover -s tests -p "test_update_stations.py" -v`
Expected: ERROR, `ImportError: cannot import name 'build'`.

- [ ] **Step 3: Change `scripts/update_stations.py`**

Replace the import block and constants at the top (current lines 8–21) with:

```python
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from station_places import (  # noqa: E402
    LAT_RANGE, LNG_RANGE, PLACES_PATH, PlacesError, apply, dump_stations, load,
)

# data.gov.tw lists /openData/getStationInfo; the server redirects that to this
FEED_URL = "https://vipmbr.cpc.com.tw/opendata/getstationinfo"
ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "site" / "data" / "stations.json"
REVIEW_DIR = ROOT / ".review"  # notes for the weekly review issue; not committed
MIN_STATIONS = 1500  # the feed had 1,962 open stations in Oct 2026
HOURS_RE = re.compile(r"^\d{2}:\d{2}-\d{2}:\d{2}$")
```

Add these two functions after `parse()`:

```python
def build(stations, places, today):
    """The published data, plus fixed stations whose CPC pin moved."""
    stations = sorted(stations, key=lambda s: s["id"])
    moved = apply(stations, places)
    return {"updated": today, "source": "https://data.gov.tw/dataset/6065", "stations": stations}, moved


def load_places_or_exit(path=PLACES_PATH):
    try:
        return load(path)
    except PlacesError as e:
        sys.exit(f"{path.name}: {e}; not updating.")
```

Replace the end of `main()` (from `stations.sort(...)` to the final `print`) with:

```python
    places = load_places_or_exit()
    taipei = timezone(timedelta(hours=8))
    data, moved = build(stations, places, datetime.now(taipei).strftime("%Y-%m-%d"))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(dump_stations(data), encoding="utf-8")
    REVIEW_DIR.mkdir(exist_ok=True)
    (REVIEW_DIR / "moved.json").write_text(json.dumps(moved), encoding="utf-8")
    with_pid = sum(1 for s in data["stations"] if "pid" in s)
    print(f"Wrote {len(stations)} stations ({with_pid} with a Google listing) to {OUT_PATH}")
    if moved:
        print(f"CPC moved {len(moved)} pin(s) that have an owner fix: {[m['id'] for m in moved]}")
```

Append `.review/` to `.gitignore`.

- [ ] **Step 4: Run all Python tests**

Run: `python3 -I -m unittest discover -s tests -p "test_*.py" -v`
Expected: all `ok`.

- [ ] **Step 5: Run the real update and check the result**

Run: `python3 -I scripts/update_stations.py && cat .review/moved.json`
Expected: `Wrote N stations (N-1 with a Google listing) …` and `[]`. Then:

```bash
python3 -I -c "
import json; d = json.load(open('site/data/stations.json', encoding='utf-8'))
s = {x['id']: x for x in d['stations']}
print(s['D5139']['lat'], s['D5139']['lng'], s['D5139'].get('pid'))
print('D4332 pid:', s['D4332'].get('pid'))"
```
Expected: `22.76437 120.2373 ChIJ…` (南寮漁船站 now in Kaohsiung) and `D4332 pid: None`.

- [ ] **Step 6: Commit**

```bash
git add scripts/update_stations.py tests/test_update_stations.py .gitignore site/data/stations.json
git commit -m "Apply Google listings and pin fixes during the data update

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Weekly matching step (`scripts/match_places.py`)

**Files:**
- Create: `scripts/match_places.py`
- Test: `tests/test_match_places.py`

**Interfaces:**
- Consumes: `place_match.FIELDS, MATCH, FAR, match_station`; `station_places.PLACES_PATH, PlacesError, dump, dump_stations, load, seen_key`.
- Produces: `MAX_PER_RUN = 50`; `todo(stations, places) -> list`; `run(stations, places, search, limit=MAX_PER_RUN) -> dict` with keys `matched: [id]`, `far: [id]`, `doubtful: [{"id", "pid": str|None, "verdict"}]`, `error: str|None`, `remaining: int`; `reviewed_changes(stations, places) -> [id]`; `far_unfixed(stations, places) -> [{"id", "pid", "far"}]`; `main()` writes `data/places.json`, `site/data/stations.json` and `.review/match.json` (the run dict plus `reviewed_changed` and `far_unfixed`), always exits 0 except on a malformed `places.json`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_match_places.py
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I -m unittest discover -s tests -p "test_match_places.py" -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'match_places'`.

- [ ] **Step 3: Write `scripts/match_places.py`**

```python
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
        if c and c["verdict"] in (MATCH, FAR):
            entry = {"pid": c["pid"], "src": "auto", "seen": seen_key(s)}
            if c["verdict"] == FAR:
                entry["far"] = c["dist"]
            places[sid] = entry
            s["pid"] = c["pid"]
            report["far" if c["verdict"] == FAR else "matched"].append(sid)
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
```

- [ ] **Step 4: Run all Python tests**

Run: `python3 -I -m unittest discover -s tests -p "test_*.py" -v`
Expected: all `ok`.

- [ ] **Step 5: Run it for real without a key (no Google calls)**

Run: `env -u PLACES_API_KEY python3 -I scripts/match_places.py && git status --short`
Expected: `Matched 0, far 0, doubtful 0, remaining 0. Warning: PLACES_API_KEY is not set; matching skipped`, and `git status` shows no change to `data/places.json` or `site/data/stations.json` (every station already has an entry). If CPC added a station since Task 3, `remaining` is that number instead; that is fine, as the weekly job will match it.

- [ ] **Step 6: Commit**

```bash
git add scripts/match_places.py tests/test_match_places.py
git commit -m "Add weekly matching of new stations to Google listings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Review issue text (`scripts/review_issue.py`)

**Files:**
- Create: `scripts/review_issue.py`
- Test: `tests/test_review_issue.py`

**Interfaces:**
- Consumes: `.review/moved.json` (list of `{"id", "cpc": [lat, lng]}`), `.review/match.json` (dict from Task 5), `site/data/stations.json`.
- Produces: `TITLE = "需要檢查的加油站"`; `build(moved: list, match: dict, stations_by_id: dict) -> str` ("" when nothing needs checking); `main()` writes `.review/issue.md`. Contains only CPC data and Google links (place IDs), never Google names or addresses.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_review_issue.py
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I -m unittest discover -s tests -p "test_review_issue.py" -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'review_issue'`.

- [ ] **Step 3: Write `scripts/review_issue.py`**

```python
"""Write .review/issue.md for the weekly 「需要檢查的加油站」 issue (empty = nothing to check)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / ".review"
STATIONS_PATH = ROOT / "site" / "data" / "stations.json"
TITLE = "需要檢查的加油站"


def _pin(lat, lng):
    return f"https://www.google.com/maps?q={lat},{lng}"


def _listing(pid):
    return f"https://www.google.com/maps/place/?q=place_id:{pid}"


def _line(stations_by_id, sid, extra=""):
    s = stations_by_id.get(sid)
    if not s:
        return f"- `{sid}`（已不在 CPC 資料中）{extra}"
    where = f"{s.get('city', '')}{s.get('district', '')}{s.get('addr', '')}"
    return f"- `{sid}` {s['name']} — {where} · [CPC 位置]({_pin(s['lat'], s['lng'])}){extra}"


def build(moved, match, stations_by_id):
    sections = []

    def section(title, lines):
        if lines:
            sections.append(f"### {title}\n\n" + "\n".join(lines))

    section("找不到或不確定的 Google 地圖配對（下週會再試）", [
        _line(stations_by_id, d["id"], f" · [Google 候選]({_listing(d['pid'])})" if d.get("pid") else "")
        for d in match.get("doubtful", [])])
    section("位置可能有誤：請在 data/places.json 為這些站加上 fix", [
        _line(stations_by_id, f["id"], f" · 相距 {f['far'] / 1000:.1f} 公里 · [Google 地圖上的位置]({_listing(f['pid'])})")
        for f in match.get("far_unfixed", [])])
    section('CPC 改了已檢查站點的名稱或地址（要重新配對，把該站的 src 改成 "auto"）', [
        _line(stations_by_id, sid) for sid in match.get("reviewed_changed", [])])
    section("CPC 移動了你修正過的站點（CPC 可能已更正；確認後可刪除該站的 fix）", [
        _line(stations_by_id, m["id"], f" · [CPC 的新位置]({_pin(*m['cpc'])})") for m in moved])
    notes = []
    if match.get("error"):
        notes.append(f"- 這次配對未完成：{match['error']}")
    if match.get("remaining"):
        notes.append(f"- 還有 {match['remaining']} 個站點等待配對（每週最多 50 個）")
    section("其他", notes)
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n\n---\n此清單由每週更新自動產生，處理完畢後會自動關閉。\n"


def main():
    def read(name, default):
        p = REVIEW_DIR / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    stations = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))["stations"]
    text = build(read("moved.json", []), read("match.json", {}), {s["id"]: s for s in stations})
    REVIEW_DIR.mkdir(exist_ok=True)
    (REVIEW_DIR / "issue.md").write_text(text, encoding="utf-8")
    print("Review issue: " + ("has items" if text else "nothing to check"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all Python tests**

Run: `python3 -I -m unittest discover -s tests -p "test_*.py" -v`
Expected: all `ok`.

- [ ] **Step 5: Run it on the real `.review/` files from Tasks 4–5**

Run: `python3 -I scripts/review_issue.py && cat .review/issue.md`
Expected: `Review issue: has items` and an 「其他」 section saying matching was skipped because `PLACES_API_KEY` is not set (from Task 5 Step 5). Nothing else.

- [ ] **Step 6: Commit**

```bash
git add scripts/review_issue.py tests/test_review_issue.py
git commit -m "Add the weekly review issue text

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Owner setup in Google Cloud and GitHub (owner does the console steps)

**Files:** none.

- [ ] **Step 1: Ask the owner to do these four things and confirm when done**

1. **Places key for the weekly job.** In Google Cloud Console → APIs & Services → Credentials, on the key in `scratch/places_key.txt` (or a new key): Application restrictions **None**; API restrictions **Places API (New)** only. (GitHub's servers change address on every run, so an IP restriction would block it.)
2. **Website key.** On the map key (the one in the `GOOGLE_MAPS_API_KEY` repository variable): add **Places API (New)** to its allowed APIs. Keep the website restriction.
3. **Daily caps.** Google Cloud Console → Google Maps Platform → Quotas → Places API (New):
   - `GetPhotoMediaRequest` per day: **33**
   - `SearchTextRequest` per day: **150**
   - `AutocompletePlaces…` and `SearchNearby…` per day: **1**
4. **Billing alert.** Billing → Budgets & alerts → create a budget of **US$1** with an alert at 100%.

- [ ] **Step 2: Store the Places key as a GitHub secret (the key never appears on screen)**

Run: `gh secret set PLACES_API_KEY -R jsnprofessor/taiwan-oil < scratch/places_key.txt && gh secret list -R jsnprofessor/taiwan-oil`
Expected: `PLACES_API_KEY` listed with today's date.

- [ ] **Step 3: Check the Places key works without an IP restriction (one free call)**

Run:
```bash
python3 -I - <<'EOF' 2>&1 | sed -E 's/AIza[0-9A-Za-z_-]{20,}/***KEY***/g'
import json, urllib.request
k = open("scratch/places_key.txt").read().strip()
req = urllib.request.Request("https://places.googleapis.com/v1/places/ChIJA-pXq72sQjQRVY0AMCPVELc",
    headers={"X-Goog-Api-Key": k, "X-Goog-FieldMask": "id"})
print(json.loads(urllib.request.urlopen(req, timeout=30).read()))
EOF
```
Expected: `{'id': 'ChIJA-pXq72sQjQRVY0AMCPVELc'}` (ID-only Place Details is free). A 403 means step 1.1 isn't done yet.

---

### Task 8: Weekly workflow and README

**Files:**
- Modify: `.github/workflows/deploy.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/match_places.py`, `scripts/review_issue.py`, secret `PLACES_API_KEY`.

- [ ] **Step 1: Edit `.github/workflows/deploy.yml`**

Add `issues: write` under `permissions:`:

```yaml
permissions:
  contents: write # commit refreshed data
  pages: write
  id-token: write
  issues: write # the 需要檢查的加油站 review issue
```

Insert before the `Download station data` step:

```yaml
      - name: Run tests
        run: |
          python3 -I -m unittest discover -s tests -p "test_*.py"
          node --test tests/*.test.js
```

Insert after the `Download station data` step:

```yaml
      # Never fails the job: problems go to the review issue instead.
      - name: Match new stations to Google Maps
        env:
          PLACES_API_KEY: ${{ secrets.PLACES_API_KEY }}
        run: python3 -I scripts/match_places.py
```

In `Commit refreshed data`, change `git add site/data/stations.json` to `git add site/data/stations.json data/places.json`.

Insert after `Commit refreshed data`:

```yaml
      - name: Update review issue
        continue-on-error: true
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python3 -I scripts/review_issue.py
          title="需要檢查的加油站"
          num=$(gh issue list --state open --limit 100 --json number,title \
            --jq ".[] | select(.title == \"$title\") | .number" | head -n1)
          if [ -s .review/issue.md ]; then
            if [ -z "$num" ]; then
              gh issue create --title "$title" --body-file .review/issue.md
            elif [ "$(gh issue view "$num" --json body --jq .body)" != "$(cat .review/issue.md)" ]; then
              gh issue edit "$num" --body-file .review/issue.md
              gh issue comment "$num" --body "清單已更新。"
            fi
          elif [ -n "$num" ]; then
            gh issue close "$num" --comment "全部處理完畢。"
          fi
```

- [ ] **Step 2: Check the YAML parses**

Run: `npx -y js-yaml .github/workflows/deploy.yml > /dev/null && echo ok`
Expected: `ok`.

- [ ] **Step 3: Update `README.md`**

In the "Files" list add:

```markdown
- `data/places.json` – each station's Google Maps listing (place ID) and owner-entered pin fixes; reviewed by hand
- `scripts/match_places.py` – weekly: matches new or changed stations to Google listings (at most 50 per run)
- `scripts/review_issue.py` – writes the 「需要檢查的加油站」 issue when something needs checking
```

In "One-time setup" add a section:

```markdown
### Station photos (Google Places API)

1. A second API key restricted to **Places API (New)**, with no application restriction, stored as the
   repository **secret** `PLACES_API_KEY` (`gh secret set PLACES_API_KEY < keyfile`).
2. Add **Places API (New)** to the website key's allowed APIs.
3. Google Maps Platform → Quotas → Places API (New): GetPhotoMedia **33/day** (stays within the free
   1,000 photos a month), SearchText **150/day**, unused methods **1/day**. Add a US$1 billing alert.
4. When the 「需要檢查的加油站」 issue opens, edit `data/places.json`: add `"fix": {"lat": …, "lng": …, "cpc": [CPC lat, CPC lng]}`
   for a wrong pin, set `"pid"` to a place ID (or `null` for not on Google), and set `"src": "reviewed"`.
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml README.md
git commit -m "Run tests, match new stations and keep a review issue in the weekly job

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 導航 uses the place ID

**Files:**
- Modify: `site/filters.js` (add `directionsUrl`)
- Modify: `site/app.js` (remove its `directionsUrl`, import it)
- Test: `tests/filters.test.js`

**Interfaces:**
- Produces: `export function directionsUrl(s: {lat, lng, pid?}) -> string` in `site/filters.js`.

- [ ] **Step 1: Write the failing test** (add to `tests/filters.test.js`; add `directionsUrl` to its import list from `../site/filters.js`)

```js
test("directionsUrl routes to the exact Google listing when a place ID is known", () => {
  const s = { lat: 25.0726, lng: 121.6084, pid: "ChIJA-pXq72sQjQRVY0AMCPVELc" };
  const url = new URL(directionsUrl(s));
  assert.equal(url.origin + url.pathname, "https://www.google.com/maps/dir/");
  assert.equal(url.searchParams.get("api"), "1");
  assert.equal(url.searchParams.get("destination"), "25.0726,121.6084");
  assert.equal(url.searchParams.get("destination_place_id"), s.pid);
  assert.equal(url.searchParams.get("travelmode"), "driving");
  assert.equal(new URL(directionsUrl({ lat: 1, lng: 2 })).searchParams.has("destination_place_id"), false);
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `node --test tests/*.test.js`
Expected: FAIL, `does not provide an export named 'directionsUrl'`.

- [ ] **Step 3: Implement**

Add to the end of `site/filters.js`:

```js
// Google Maps directions; the place ID routes to the station's own listing
// (e.g. the right side of a highway service area), coordinates are the fallback.
export function directionsUrl(s) {
  const params = new URLSearchParams({ api: "1", destination: `${s.lat},${s.lng}`, travelmode: "driving" });
  if (s.pid) params.set("destination_place_id", s.pid);
  return `https://www.google.com/maps/dir/?${params}`;
}
```

In `site/app.js`: delete the `function directionsUrl(s) { … }` block, and add `directionsUrl` to the import from `./filters.js?v=__BUILD__`.

- [ ] **Step 4: Run the tests**

Run: `node --test tests/*.test.js && python3 -I -m unittest discover -s tests -p "test_*.py"`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add site/filters.js site/app.js tests/filters.test.js
git commit -m "Route 導航 to the station's Google listing

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Photos in the station card, browser check, release

**Files:**
- Create: `site/photos.js`
- Modify: `site/app.js` (import; one line in `renderStation`)
- Modify: `site/style.css` (photo styles)

**Interfaces:**
- Consumes: station objects with optional `pid`; the `#i-pump` icon in `index.html`; `google.maps.importLibrary("places")` → `{ Place }`; `Place#fetchFields({fields: ["photos"]})`; `Photo#getURI({maxWidth})`; `Photo#authorAttributions[] {displayName, uri}`.
- Produces: `export function photoSection(pid: string) -> HTMLElement`.

- [ ] **Step 1: Write `site/photos.js`**

```js
// Station photos from Google Places. Each image counts toward the daily free quota,
// so only the photo on screen is requested. Google allows no caching of photos or
// their URLs, so the list is fetched fresh every time a card opens (that request is free).

const PHOTO_WIDTH = 800;
let Place = null;

async function placePhotos(pid) {
  Place ??= (await google.maps.importLibrary("places")).Place;
  const place = new Place({ id: pid });
  await place.fetchFields({ fields: ["photos"] }); // id + photos only: the free tier
  return place.photos ?? [];
}

function node(tag, className, ...children) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  n.append(...children);
  return n;
}

function link(href, text) {
  const a = node("a", "", text);
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener";
  return a;
}

function message(text) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-pump");
  svg.append(use);
  return node("div", "st-photo-msg", svg, node("span", "", text));
}

function slide(photo) {
  const img = node("img", "");
  img.alt = "";
  img.decoding = "async";
  const fig = node("figure", "st-photo", img);
  const author = photo.authorAttributions?.[0];
  if (author) {
    fig.append(node("figcaption", "st-photo-author", "相片：",
      author.uri ? link(author.uri, author.displayName) : author.displayName));
  }
  img.addEventListener("error", () => fig.replaceChildren(message("相片暫時無法顯示")), { once: true });
  const load = () => { if (!img.getAttribute("src")) img.src = photo.getURI({ maxWidth: PHOTO_WIDTH }); };
  return { fig, load };
}

async function fill(box, pid) {
  let photos = null;
  try {
    photos = await placePhotos(pid);
  } catch {
    // network or quota: shown below
  }
  if (!box.isConnected) return; // another station's card has replaced this one
  if (photos === null) return box.replaceChildren(message("相片暫時無法顯示"));
  if (photos.length === 0) return box.replaceChildren(message("暫無相片"));

  const slides = photos.map(slide);
  const strip = node("div", "st-photo-strip", ...slides.map((s) => s.fig));
  const count = node("div", "st-photo-count");
  const observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const i = slides.findIndex((s) => s.fig === e.target);
      slides[i].load();
      count.textContent = slides.length > 1 ? `${i + 1} / ${slides.length}` : "";
    }
  }, { root: strip, threshold: 0.6 });
  slides.forEach((s) => observer.observe(s.fig));
  box.replaceChildren(strip, count);
}

// Reserves a 16:9 area straight away so the card doesn't jump when photos arrive.
export function photoSection(pid) {
  const box = node("div", "st-photos");
  box.setAttribute("aria-label", "加油站相片");
  fill(box, pid);
  const listing = `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(pid)}`;
  return node("div", "st-photo-block", box,
    node("div", "st-photo-credit", node("span", "", "Google Maps"), link(listing, "在 Google 地圖查看更多相片")));
}
```

- [ ] **Step 2: Use it in `site/app.js`**

Add the import after the `filters.js` import:

```js
import { photoSection } from "./photos.js?v=__BUILD__";
```

In `renderStation`, directly after the `el("div", { class: "st-tags" }, … ),` entry, add:

```js
    s.pid && photoSection(s.pid),
```

(The photo sits under the name and tags, not at the very top, so the sheet's close button and handle never cover it.)

- [ ] **Step 3: Add the styles to `site/style.css`** (after the `.st-distance` rule)

```css
/* Station photos */

.st-photo-block { margin: 0 0 14px; }

.st-photos {
  position: relative;
  aspect-ratio: 16 / 9;
  border-radius: 14px;
  overflow: hidden;
  background: var(--surface-2);
}

.st-photo-strip {
  display: flex;
  height: 100%;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  overscroll-behavior-x: contain;
  scrollbar-width: none;
}

.st-photo-strip::-webkit-scrollbar { display: none; }

.st-photo {
  position: relative;
  flex: 0 0 100%;
  margin: 0;
  scroll-snap-align: center;
}

.st-photo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.st-photo-author {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 18px 10px 6px;
  font-size: 12px;
  color: #fff;
  background: linear-gradient(transparent, rgba(0, 0, 0, .55));
}

.st-photo-author a { color: inherit; }

.st-photo-count {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, .55);
  color: #fff;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.st-photo-count:empty { display: none; }

.st-photo-msg {
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 6px;
  height: 100%;
  color: var(--text-2);
  font-size: 14px;
}

.st-photo-msg svg { width: 32px; height: 32px; }

.st-photo-credit {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-2);
}

.st-photo-credit a { color: var(--accent); }
```

- [ ] **Step 4: Run all tests**

Run: `node --test tests/*.test.js && python3 -I -m unittest discover -s tests -p "test_*.py"`
Expected: all pass.

- [ ] **Step 5: Browser check with the real key** (needs Task 7 step 1.2 done)

Start the preview:
```bash
(GOOGLE_MAPS_API_KEY="$(gh variable get GOOGLE_MAPS_API_KEY -R jsnprofessor/taiwan-oil)" \
 GOOGLE_MAP_ID="$(gh variable get GOOGLE_MAP_ID -R jsnprofessor/taiwan-oil)" \
 scripts/serve_local.sh >/dev/null 2>&1 &); sleep 2
```

With Playwright at 390×844, record every request whose URL contains `/photos/` and `/media`, then check each item; all must hold:

1. Search 「康寧」, click the marker `gmp-advanced-marker[title="康寧"]`: `.st-photos` appears at once; within 5 s it contains an `img` with a `src`; exactly **1** media request so far; a `figcaption` starting 「相片：」 with a link; 「Google Maps」 credit text at ≥12 px; the 導航 link contains `destination_place_id=`.
2. `#station` height measured 100 ms after opening equals its height after photos loaded (no jump).
3. Scroll `.st-photo-strip` by its own width: after 1 s, exactly **2** media requests in total; the counter reads `2 / N`.
4. Search 「箔子寮」 and open it: no `.st-photos` element in the card.
5. Route `**/photos/**/media**` to answer HTTP 429, reopen 康寧: the slide shows 「相片暫時無法顯示」 and no broken `img`.
6. Race: open 康寧, and within 100 ms open 東湖 (`gmp-advanced-marker[title="東湖站"]`, search 「東湖」 first if needed): after 3 s exactly one `.st-photos` exists in the page and no page errors.
7. Dark mode (`colorScheme: 'dark'`): screenshot the open card; the placeholder and credit are readable.
8. No page errors or console errors in any of the above.

If any item fails, stop and fix before continuing. Then stop the server: `pkill -f "http.server 8000"`, and delete `scratch/_site` and `.playwright-mcp/`.

- [ ] **Step 6: Commit**

```bash
git add site/photos.js site/app.js site/style.css
git commit -m "Show swipeable Google photos in the station card

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Ask the owner before pushing**

Summarize the commits and ask: "Push now? It deploys the site and runs the weekly job once."

- [ ] **Step 8: After the owner says yes: push and watch**

```bash
git push
sleep 5
id=$(gh run list -R jsnprofessor/taiwan-oil --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$id" -R jsnprofessor/taiwan-oil --exit-status
gh run view "$id" -R jsnprofessor/taiwan-oil --log | grep -E "Ran [0-9]+ tests|tests [0-9]+|Wrote [0-9]+ stations|Matched|Review issue"
gh issue list -R jsnprofessor/taiwan-oil --state open
```
Expected: run succeeds; Python and Node tests ran; `Wrote N stations (N-1 with a Google listing)`; `Matched 0, …` with no warning; `Review issue: nothing to check`; no open 「需要檢查的加油站」 issue.

- [ ] **Step 9: Live check**

Open https://jsnprofessor.github.io/taiwan-oil/ in Playwright, search 「康寧」, open it: a photo loads and the credit shows. Then ask the owner to check on the iPhone (swipe, credit link, 導航 opens the station's listing in Google Maps).

- [ ] **Step 10: Cleanup (after the live check)**

```bash
rm -rf scratch/review scratch/match-test scratch/seed_places.py
ls -A scratch
```
Ask the owner whether to delete `scratch/places_key.txt` (the secret now holds the key). Delete it if they agree.
