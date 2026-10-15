// Filter rules for the station map. No DOM or Google Maps code here, so the
// rules can be tested with `node --test tests/`.

export const TYPES = [
  { key: "all", label: "全部" },
  { key: "自營站", label: "自營" },
  { key: "加盟站", label: "加盟" },
  { key: "漁船站", label: "漁船" },
];

export const FILTER_GROUPS = [
  { label: "營業", options: [
    { key: "openNow", label: "營業中" },
    { key: "allDay", label: "24小時" },
  ] },
  { label: "油品", options: [
    { key: "u92", label: "92無鉛" },
    { key: "u95", label: "95無鉛" },
    { key: "u98", label: "98無鉛" },
    { key: "e3", label: "酒精汽油" },
    { key: "diesel", label: "超級柴油" },
    { key: "kero", label: "煤油" },
  ] },
  { label: "服務", options: [
    { key: "self", label: "自助加油" },
    { key: "selfDiesel", label: "自助柴油" },
    { key: "wash", label: "洗車" },
    { key: "service", label: "保養" },
    { key: "etag", label: "eTag" },
    { key: "hwy", label: "國道" },
  ] },
  { label: "付款", options: [
    { key: "member", label: "會員卡" },
    { key: "easycard", label: "悠遊卡" },
    { key: "ipass", label: "一卡通" },
    { key: "happycash", label: "HappyCash" },
    { key: "einv", label: "電子發票" },
  ] },
];

const taipeiClock = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Taipei", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

function minutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function isAllDay(s) {
  return s.hours === "00:00-24:00";
}

// true / false, or null when hours are unknown
export function isOpenNow(s, now = new Date()) {
  if (!s.hours) return null;
  if (isAllDay(s)) return true;
  const [start, end] = s.hours.split("-").map(minutes);
  const t = minutes(taipeiClock.format(now));
  return start <= end ? t >= start && t < end : t >= start || t < end;
}

function hasOption(s, key, now) {
  if (key === "openNow") return isOpenNow(s, now) === true;
  if (key === "allDay") return isAllDay(s);
  return Boolean(s[key]);
}

function matchesText(s, query) {
  if (!query) return true;
  const q = query.trim().toLowerCase();
  return `${s.name} ${s.city}${s.district}${s.addr}`.toLowerCase().includes(q);
}

// state: { type: "all" | type name, keys: Set of option keys, query: string }
export function matches(s, state, now = new Date()) {
  if (state.type !== "all" && s.type !== state.type) return false;
  if (!matchesText(s, state.query)) return false;
  for (const key of state.keys) if (!hasOption(s, key, now)) return false;
  return true;
}

// How many stations each choice would show, given the rest of the state.
export function optionCounts(stations, state, now = new Date()) {
  const types = Object.fromEntries(TYPES.map((t) => [t.key, 0]));
  const options = {};
  for (const g of FILTER_GROUPS) for (const o of g.options) options[o.key] = 0;
  let total = 0;

  const anyType = { ...state, type: "all" };
  for (const s of stations) {
    if (matches(s, anyType, now)) {
      types.all++;
      if (s.type in types) types[s.type]++;
    }
    if (matches(s, state, now)) {
      total++;
      for (const key in options) if (hasOption(s, key, now)) options[key]++;
    }
  }
  return { types, options, total };
}

export function distanceKm(p, q) {
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(q.lat - p.lat);
  const dLng = rad(q.lng - p.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(p.lat)) * Math.cos(rad(q.lat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

// "台灣中油 康寧站, 台北市內湖區康寧路三段30號": Google's recommended way to name a
// place in Maps links, without CPC's notes such as (備註:…).
export function placeLabel(s) {
  // drop notes in brackets, then any unmatched bracket left in CPC's data
  const withoutNotes = (text) => text.replace(/[（(][^)）]*[)）]/g, "").replace(/[()（）]/g, "").trim();
  const base = withoutNotes(s.name);
  const name = base.endsWith("站") ? base : `${base}站`;
  const addr = withoutNotes(s.addr || "");
  const where = addr.startsWith(s.city) ? addr : `${s.city}${s.district || ""}${addr}`;
  return `台灣中油 ${name}, ${where}`;
}

// Google Maps directions. The Google Maps iPhone app ignores place IDs in links, so the
// destination names the station; the place ID still picks the exact listing elsewhere.
// Stations without a Google listing fall back to coordinates.
export function directionsUrl(s) {
  const params = new URLSearchParams({ api: "1", travelmode: "driving" });
  if (s.pid) {
    params.set("destination", placeLabel(s));
    params.set("destination_place_id", s.pid);
  } else {
    params.set("destination", `${s.lat},${s.lng}`);
  }
  return `https://www.google.com/maps/dir/?${params}`;
}

// The station's Google listing (photos, reviews), in the documented search format.
export function placeUrl(s) {
  const params = new URLSearchParams({ api: "1", query: placeLabel(s), query_place_id: s.pid });
  return `https://www.google.com/maps/search/?${params}`;
}
