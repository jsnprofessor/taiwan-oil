#!/usr/bin/env python3
"""Download CPC (台灣中油) station data and write site/data/stations.json.

Source: 台灣中油公司加油站服務資訊, https://data.gov.tw/dataset/6065
Uses only the Python standard library. Exits non-zero if the feed looks wrong,
so a bad download never replaces good data.
"""
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

# Feed field -> short key. Value 1 means the station offers it.
FLAGS = {
    "無鉛92": "u92",
    "無鉛95": "u95",
    "無鉛98": "u98",
    "酒精汽油": "e3",
    "煤油": "kero",
    "超柴": "diesel",
    "國道高速公路": "hwy",
    "刷卡自助": "self",
    "自助柴油站": "selfDiesel",
    "會員卡": "member",
    "電子發票": "einv",
    "悠遊卡": "easycard",
    "一卡通": "ipass",
    "HappyCash": "happycash",
}


def text(row, tag):
    # the feed mixes types: flags are numbers (1), 營業中 is text ("1")
    value = row.get(tag)
    return "" if value is None else str(value).strip()


def parse(json_bytes):
    rows = json.loads(json_bytes.decode("utf-8-sig"))  # tolerate a byte-order mark
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        sys.exit("Feed is not a list of stations; not updating.")
    stations, skipped = [], []
    for row in rows:
        # 1 = open; 3 = not operating (CPC also leaves these out of its other station lists)
        if text(row, "營業中") != "1":
            continue
        name = text(row, "站名")
        try:
            lat, lng = float(text(row, "緯度")), float(text(row, "經度"))
        except ValueError:
            skipped.append(name)
            continue
        if not (LAT_RANGE[0] < lat < LAT_RANGE[1] and LNG_RANGE[0] < lng < LNG_RANGE[1]):
            skipped.append(name)
            continue
        hours = text(row, "營業時間")
        station = {
            "id": text(row, "站代號"),
            "name": name,
            "type": text(row, "類別"),
            "city": text(row, "縣市"),
            "district": text(row, "鄉鎮區"),
            "addr": text(row, "地址"),
            "phone": text(row, "電話"),
            "hours": hours if HOURS_RE.match(hours) else "",
            "hoursRaw": "" if HOURS_RE.match(hours) else hours,
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "wash": text(row, "洗車類別"),
            "service": text(row, "保養間時間"),
            "etag": text(row, "etag申裝儲值時間"),
        }
        station.update({key: 1 for tag, key in FLAGS.items() if text(row, tag) == "1"})
        stations.append({k: v for k, v in station.items() if v != ""})
    return stations, skipped


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


def main():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "taiwan-oil-station-map"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        json_bytes = resp.read()

    stations, skipped = parse(json_bytes)
    if skipped:
        print(f"Skipped {len(skipped)} stations with bad coordinates: {skipped[:20]}")
    if len(stations) < MIN_STATIONS:
        sys.exit(f"Only {len(stations)} open stations (expected >= {MIN_STATIONS}); not updating.")

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


if __name__ == "__main__":
    main()
