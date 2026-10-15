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

# data.gov.tw lists /openData/getStationInfo; the server redirects that to this
FEED_URL = "https://vipmbr.cpc.com.tw/opendata/getstationinfo"
OUT_PATH = Path(__file__).resolve().parent.parent / "site" / "data" / "stations.json"
MIN_STATIONS = 1500  # the feed had 1,962 open stations in Oct 2026
# Box around Taiwan, Penghu, Kinmen and Matsu
LAT_RANGE = (21.5, 26.5)
LNG_RANGE = (118.0, 122.5)
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


def main():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "taiwan-oil-station-map"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        json_bytes = resp.read()

    stations, skipped = parse(json_bytes)
    if skipped:
        print(f"Skipped {len(skipped)} stations with bad coordinates: {skipped[:20]}")
    if len(stations) < MIN_STATIONS:
        sys.exit(f"Only {len(stations)} open stations (expected >= {MIN_STATIONS}); not updating.")

    stations.sort(key=lambda s: s["id"])
    taipei = timezone(timedelta(hours=8))
    data = {
        "updated": datetime.now(taipei).strftime("%Y-%m-%d"),
        "source": "https://data.gov.tw/dataset/6065",
        "stations": stations,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(stations)} stations to {OUT_PATH}")


if __name__ == "__main__":
    main()
