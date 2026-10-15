import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  FILTER_GROUPS, TYPES, isOpenNow, matches, optionCounts, distanceKm,
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
