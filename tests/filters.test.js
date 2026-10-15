import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  FILTER_GROUPS, TYPES, isOpenNow, matches, optionCounts, distanceKm, directionsUrl, placeLabel, placeUrl,
} from "../site/filters.js";

// 2026-10-15 12:00 in Taiwan
const NOON = new Date("2026-10-15T04:00:00Z");
// 2026-10-15 23:30 in Taiwan
const LATE = new Date("2026-10-15T15:30:00Z");

const a = { id: "a", name: "台東", type: "加盟站", city: "台東縣", district: "台東市", addr: "中華路", hours: "06:30-21:30", u98: 1, easycard: 1 };
const b = { id: "b", name: "蘭嶼", type: "自營站", city: "台東縣", district: "蘭嶼鄉", addr: "椰油村", hours: "00:00-24:00", diesel: 1 };
const c = { id: "c", name: "夜貓", type: "自營站", city: "台北市", district: "中山區", addr: "長安路", hours: "22:00-02:00", u98: 1 };
const all = [a, b, c];
const state = (o = {}) => ({ type: "all", keys: new Set(), query: "", ...o });

test("isOpenNow handles normal, 24h, overnight and unknown hours", () => {
  assert.equal(isOpenNow(a, NOON), true);
  assert.equal(isOpenNow(a, LATE), false);
  assert.equal(isOpenNow(b, LATE), true);
  assert.equal(isOpenNow(c, LATE), true);
  assert.equal(isOpenNow(c, NOON), false);
  assert.equal(isOpenNow({ hoursRaw: "依公告" }, NOON), null);
});

test("matches requires every selected option (AND)", () => {
  assert.equal(matches(a, state({ keys: new Set(["u98", "easycard"]) }), NOON), true);
  assert.equal(matches(c, state({ keys: new Set(["u98", "easycard"]) }), NOON), false);
});

test("matches filters by type and search text", () => {
  assert.deepEqual(all.filter((s) => matches(s, state({ type: "自營站" }), NOON)).map((s) => s.id), ["b", "c"]);
  assert.deepEqual(all.filter((s) => matches(s, state({ query: "台東" }), NOON)).map((s) => s.id), ["a", "b"]);
  assert.deepEqual(all.filter((s) => matches(s, state({ query: "長安" }), NOON)).map((s) => s.id), ["c"]);
});

test("openNow and allDay options use the clock", () => {
  assert.deepEqual(all.filter((s) => matches(s, state({ keys: new Set(["openNow"]) }), LATE)).map((s) => s.id), ["b", "c"]);
  assert.deepEqual(all.filter((s) => matches(s, state({ keys: new Set(["allDay"]) }), NOON)).map((s) => s.id), ["b"]);
});

test("optionCounts shows what each choice would give", () => {
  const counts = optionCounts(all, state({ keys: new Set(["u98"]) }), NOON);
  // type counts respect other filters (u98) but ignore the current type
  assert.deepEqual(counts.types, { all: 2, 加盟站: 1, 自營站: 1, 漁船站: 0 });
  // option counts = current results narrowed by that option
  assert.equal(counts.options.easycard, 1);
  assert.equal(counts.options.diesel, 0);
  assert.equal(counts.options.u98, 2);
  assert.equal(counts.total, 2);
});

test("distanceKm is roughly right", () => {
  // Taipei Main Station to Kaohsiung Main Station ≈ 297 km in a straight line
  const d = distanceKm({ lat: 25.0478, lng: 121.5170 }, { lat: 22.6394, lng: 120.3025 });
  assert.ok(d > 285 && d < 310, `got ${d}`);
});

test("every filter option matches at least one station in the real data", () => {
  const data = JSON.parse(readFileSync(new URL("../site/data/stations.json", import.meta.url)));
  const counts = optionCounts(data.stations, state(), NOON);
  assert.equal(counts.total, data.stations.length);
  for (const t of TYPES) assert.ok(counts.types[t.key] > 0, `type ${t.key} is empty`);
  for (const group of FILTER_GROUPS) {
    for (const o of group.options) assert.ok(counts.options[o.key] > 0, `option ${o.key} is empty`);
  }
});

const KANGNING = {
  name: "康寧", city: "台北市", district: "內湖區", addr: "康寧路三段30號",
  lat: 25.0726, lng: 121.6084, pid: "ChIJA-pXq72sQjQRVY0AMCPVELc",
};

test("placeLabel is the station's name and address, without CPC's notes", () => {
  assert.equal(placeLabel(KANGNING), "台灣中油 康寧站, 台北市內湖區康寧路三段30號");
  assert.equal(placeLabel({ name: "鎖港漁船站", city: "澎湖縣", addr: "馬公市鎖港里293號(備註:星期六日暫停營業)" }),
    "台灣中油 鎖港漁船站, 澎湖縣馬公市鎖港里293號");
  assert.equal(placeLabel({ name: "忠孝路", city: "嘉義市", district: "東區", addr: "嘉義市東區忠孝路808號" }),
    "台灣中油 忠孝路站, 嘉義市東區忠孝路808號");
  assert.equal(placeLabel({ name: "將軍漁船站(僅星期一營業)", city: "台南市", district: "將軍區", addr: "長沙里126-6號" }),
    "台灣中油 將軍漁船站, 台南市將軍區長沙里126-6號");
  assert.equal(placeLabel({ name: "四維三路站(愛心站)", city: "高雄市", district: "苓雅區", addr: "永定街93號" }),
    "台灣中油 四維三路站, 高雄市苓雅區永定街93號");
  assert.equal(placeLabel({ name: "民族", city: "高雄市", district: "三民區", addr: "民族一路418號)" }),
    "台灣中油 民族站, 高雄市三民區民族一路418號");
});

// The Google Maps iPhone app ignores place IDs in links, so the destination must
// name the station; the place ID still helps where it is supported.
test("directionsUrl names the station when it has a Google listing", () => {
  const url = new URL(directionsUrl(KANGNING));
  assert.equal(url.origin + url.pathname, "https://www.google.com/maps/dir/");
  assert.equal(url.searchParams.get("api"), "1");
  assert.equal(url.searchParams.get("destination"), placeLabel(KANGNING));
  assert.equal(url.searchParams.get("destination_place_id"), KANGNING.pid);
  assert.equal(url.searchParams.get("travelmode"), "driving");
});

test("directionsUrl uses coordinates for a station without a Google listing", () => {
  const url = new URL(directionsUrl({ ...KANGNING, pid: undefined }));
  assert.equal(url.searchParams.get("destination"), "25.0726,121.6084");
  assert.equal(url.searchParams.has("destination_place_id"), false);
});

test("placeUrl opens the station's Google listing in the documented search format", () => {
  const url = new URL(placeUrl(KANGNING));
  assert.equal(url.origin + url.pathname, "https://www.google.com/maps/search/");
  assert.equal(url.searchParams.get("api"), "1");
  assert.equal(url.searchParams.get("query"), placeLabel(KANGNING));
  assert.equal(url.searchParams.get("query_place_id"), KANGNING.pid);
});
