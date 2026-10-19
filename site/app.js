import {
  TYPES, FILTER_GROUPS, isAllDay, isOpenNow, matches, optionCounts, distanceKm, directionsUrl, placeUrl,
} from "./filters.js?v=__BUILD__";
import { photoSection } from "./photos.js?v=__BUILD__";
import { attachSheetDrag } from "./sheet.js?v=__BUILD__";

const TAIWAN_BOUNDS = { south: 21.9, west: 119.4, north: 25.3, east: 122.0 };
const TYPE_STORAGE_KEY = "stationType";
const FUEL_LABELS = [
  ["u92", "92無鉛"], ["u95", "95無鉛"], ["u98", "98無鉛"],
  ["e3", "酒精汽油"], ["diesel", "超級柴油"], ["kero", "煤油"],
];
const PAY_LABELS = [
  ["member", "會員卡"], ["easycard", "悠遊卡"], ["ipass", "一卡通"],
  ["happycash", "HappyCash"], ["einv", "電子發票"],
];
// Google Maps' own pin shape; the same blue in light and dark mode, like Google's pins
const PIN_COLORS = {
  open: { background: "#1a66d9", borderColor: "#0f4fae" },
  closed: { background: "#9aa3ae", borderColor: "#7d8691" },
};

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v; // only used with constant markup
    else node.setAttribute(k, v);
  }
  node.append(...children.filter((c) => c != null && c !== "" && c !== false));
  return node;
}

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

let toastTimer;
function toast(message, ms = 3000) {
  const t = $("toast");
  t.textContent = message;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

/* ---------- Sheets ---------- */

let openSheetId = null;
const sheetCloseHandlers = {};

function openSheet(id) {
  if (openSheetId && openSheetId !== id) closeSheet(openSheetId);
  openSheetId = id;
  const sheet = $(id);
  sheetDrags[id].open(); // after the content is filled, before it shows
  sheet.classList.add("open");
  sheet.setAttribute("aria-hidden", "false");
  sheet.scrollTop = 0;
  document.body.classList.add("sheet-open");
  // the station card leaves the map usable; other sheets dim it
  $("scrim").hidden = id === "station";
}

function closeSheet(id = openSheetId) {
  if (!id) return;
  $(id).classList.remove("open");
  $(id).setAttribute("aria-hidden", "true");
  if (openSheetId === id) openSheetId = null;
  document.body.classList.remove("sheet-open");
  $("scrim").hidden = true;
  sheetDrags[id].closed();
  sheetCloseHandlers[id]?.();
}

// The station card has half and full heights; the shorter sheets only drag down to close.
const sheetDrags = Object.fromEntries(["station", "filters", "about"].map((id) =>
  [id, attachSheetDrag($(id), () => closeSheet(id), { hasHalf: id === "station" })]));

document.querySelectorAll(".sheet [data-close]").forEach((b) =>
  b.addEventListener("click", () => closeSheet(b.closest(".sheet").id)));
$("scrim").addEventListener("click", () => closeSheet());
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
$("credit-open").addEventListener("click", () => {
  // TEMPORARY: status-bar diagnostic (see the logger in index.html)
  $("diag-log").textContent = JSON.parse(localStorage.getItem("schemeLog") || "[]").join("\n");
  openSheet("about");
});
$("diag-clear").addEventListener("click", () => {
  localStorage.removeItem("schemeLog");
  $("diag-log").textContent = "";
});

/* ---------- Station card ---------- */


function formatDistance(km) {
  return km < 1 ? `${Math.round(km * 1000)} 公尺` : `${km.toFixed(km < 10 ? 1 : 0)} 公里`;
}

function renderStation(s, myPos) {
  const open = isOpenNow(s);
  const fuels = FUEL_LABELS.filter(([k]) => s[k]).map(([, l]) => l);
  const pays = PAY_LABELS.filter(([k]) => s[k]).map(([, l]) => l);
  const services = [
    s.self && "自助加油",
    s.selfDiesel && "自助柴油",
    s.hwy && "國道服務區",
  ].filter(Boolean);
  const tel = (s.phone || "").replace(/[^\d#]/g, "");
  const hours = isAllDay(s) ? "24 小時營業" : (s.hours || s.hoursRaw || "未提供");
  const chips = (items) => el("div", { class: "chips" }, ...items.map((t) => el("span", { class: "chip" }, t)));

  $("station-body").replaceChildren(...[
    el("h2", { class: "st-title" }, s.name.endsWith("站") ? s.name : `${s.name}站`),
    el("div", { class: "st-tags" },
      el("span", { class: "tag type" }, s.type),
      open === true && el("span", { class: "tag open" }, "營業中"),
      open === false && el("span", { class: "tag closed" }, "休息中"),
      myPos && el("span", { class: "st-distance" }, formatDistance(distanceKm(myPos, s))),
    ),
    s.pid && photoSection(s.pid, placeUrl(s)),
    el("ul", { class: "st-rows" },
      el("li", {}, icon("place"), `${s.city}${s.district}${s.addr}`),
      el("li", {}, icon("clock"), hours),
      s.wash && el("li", {}, icon("info"), `洗車：${s.wash}`),
      s.service && el("li", {}, icon("info"), `保養：${s.service}`),
      s.etag && el("li", {}, icon("info"), `eTag：${s.etag}`),
    ),
    fuels.length > 0 && el("div", { class: "st-section" }, "油品"),
    fuels.length > 0 && chips(fuels),
    services.length > 0 && el("div", { class: "st-section" }, "服務"),
    services.length > 0 && chips(services),
    pays.length > 0 && el("div", { class: "st-section" }, "付款方式"),
    pays.length > 0 && chips(pays),
    el("div", { class: "st-actions sheet-foot" },
      el("a", { class: "btn btn-primary", href: directionsUrl(s), target: "_blank", rel: "noopener" }, icon("nav"), "導航"),
      tel && el("a", { class: "btn btn-secondary", href: `tel:${tel}` }, icon("phone"), "撥打電話"),
    ),
  ].filter(Boolean));
  openSheet("station");
}

/* ---------- Main ---------- */

async function main() {
  // Draw the type selector before waiting on Maps and data so the header
  // doesn't grow when they arrive. Counts and click handlers come later.
  const savedType = TYPES.some((t) => t.key === localStorage.getItem(TYPE_STORAGE_KEY))
    ? localStorage.getItem(TYPE_STORAGE_KEY) : "all";
  const typeButtons = TYPES.map((t) => el("button",
    { type: "button", role: "radio", "data-type": t.key, "aria-checked": String(t.key === savedType) },
    el("span", { class: "label" }, t.label),
    el("span", { class: "count" }, "\u00a0"))); // keeps the count line's height
  $("types").replaceChildren(...typeButtons);

  const [{ Map }, { AdvancedMarkerElement, PinElement }, data] = await Promise.all([
    google.maps.importLibrary("maps"),
    google.maps.importLibrary("marker"),
    fetch("data/stations.json").then((r) => {
      if (!r.ok) throw new Error(`stations.json: HTTP ${r.status}`);
      return r.json();
    }),
  ]);
  $("updated").textContent = data.updated;

  const map = new Map($("map"), {
    center: { lat: 23.7, lng: 120.95 },
    zoom: 7,
    mapId: window.MAP_ID,
    colorScheme: "FOLLOW_SYSTEM",
    isFractionalZoomEnabled: true,
    gestureHandling: "greedy", // one-finger pan on phones
    clickableIcons: false,
    disableDefaultUI: true,
  });

  const topPadding = () => $("map").clientHeight > 0 ? document.querySelector(".top").offsetHeight + 10 : 0;
  const fitTaiwan = () => map.fitBounds(TAIWAN_BOUNDS, { top: topPadding(), bottom: 30, left: 10, right: 10 });
  fitTaiwan();
  // camera moves made before the first idle get overridden by the initial fit
  const mapReady = new Promise((resolve) => google.maps.event.addListenerOnce(map, "idle", resolve));

  // ----- markers -----
  const state = {
    type: savedType,
    keys: new Set(),
    query: "",
  };
  let myPos = null;
  let selected = null;

  // white pump from the page's icon sprite, as an image for the pin's glyph
  const pumpPath = document.querySelector("#i-pump path").getAttribute("d");
  const pinGlyph = "data:image/svg+xml," + encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960"><path fill="#fff" d="${pumpPath}"/></svg>`);
  const paintPin = (e) => Object.assign(e.pin,
    e.closed && e !== selected ? PIN_COLORS.closed : PIN_COLORS.open,
    { scale: e === selected ? 1.3 : 1 });

  const entries = data.stations.map((s) => {
    const pin = new PinElement({ glyphSrc: pinGlyph, ...PIN_COLORS.open });
    const marker = new AdvancedMarkerElement({
      position: { lat: s.lat, lng: s.lng },
      title: s.name,
      gmpClickable: true,
    });
    marker.append(pin);
    const entry = { s, marker, pin, closed: false };
    marker.addEventListener("gmp-click", () => {
      const previous = selected;
      selected = entry;
      if (previous) paintPin(previous);
      paintPin(entry);
      marker.zIndex = 1;
      renderStation(s, myPos);
      // if the card covers the pin, move the map so the pin sits in the visible area
      const sheetTop = window.innerHeight - $("station").offsetHeight;
      const headerBottom = document.querySelector(".top").getBoundingClientRect().bottom;
      const pinY = pin.getBoundingClientRect().bottom;
      if (pinY > sheetTop - 16 || pinY < headerBottom + 40) {
        map.panBy(0, pinY - (headerBottom + sheetTop) / 2);
      }
    });
    return entry;
  });

  sheetCloseHandlers.station = () => {
    const previous = selected;
    selected = null;
    if (previous) {
      previous.marker.zIndex = null;
      paintPin(previous);
    }
  };

  const clusterer = new markerClusterer.MarkerClusterer({
    map,
    // larger radius = fewer, calmer clusters; show single pins from street level
    algorithm: new markerClusterer.SuperClusterAlgorithm({ radius: 100, maxZoom: 14 }),
    renderer: {
      render({ count, position }) {
        const size = count < 10 ? 36 : count < 100 ? 42 : 50;
        const content = el("div", { class: "cluster" }, String(count));
        content.style.cssText = `width:${size}px;height:${size}px;font-size:${size < 40 ? 13 : 14}px`;
        return new AdvancedMarkerElement({ position, content, zIndex: 1000 + count, title: `${count} 個加油站` });
      },
    },
  });

  // ----- type selector -----
  typeButtons.forEach((b, i) => b.addEventListener("click", () => {
    state.type = TYPES[i].key;
    localStorage.setItem(TYPE_STORAGE_KEY, TYPES[i].key);
    apply();
  }));

  // ----- filter sheet -----
  const chipButtons = {};
  $("filter-groups").replaceChildren(...FILTER_GROUPS.map((g) =>
    el("div", { class: "filter-group" },
      el("h3", {}, g.label),
      el("div", { class: "chips" }, ...g.options.map((o) => {
        const b = el("button", { type: "button", class: "filter-chip", "aria-pressed": "false" },
          el("span", {}, o.label), el("span", { class: "count" }, ""));
        b.addEventListener("click", () => {
          if (state.keys.has(o.key)) state.keys.delete(o.key);
          else state.keys.add(o.key);
          apply();
        });
        chipButtons[o.key] = b;
        return b;
      })),
    )));
  $("filter-open").addEventListener("click", () => openSheet("filters"));
  $("filter-clear").addEventListener("click", () => { state.keys.clear(); apply(); });

  // ----- apply state -----
  let lastShown = null;
  function apply({ fit = false } = {}) {
    const now = new Date();
    const counts = optionCounts(data.stations, state, now);

    typeButtons.forEach((b, i) => {
      const key = TYPES[i].key;
      b.setAttribute("aria-checked", String(state.type === key));
      b.querySelector(".count").textContent = counts.types[key].toLocaleString();
    });
    for (const [key, b] of Object.entries(chipButtons)) {
      const on = state.keys.has(key);
      b.setAttribute("aria-pressed", String(on));
      b.querySelector(".count").textContent = counts.options[key].toLocaleString();
      b.disabled = !on && counts.options[key] === 0;
    }
    $("filter-badge").hidden = state.keys.size === 0;
    $("filter-badge").textContent = state.keys.size;
    $("filter-open").classList.toggle("active", state.keys.size > 0);
    $("filter-apply").textContent = `顯示 ${counts.total.toLocaleString()} 站`;

    const shown = entries.filter((e) => matches(e.s, state, now));
    for (const e of entries) {
      const closed = isOpenNow(e.s, now) === false;
      if (closed !== e.closed) {
        e.closed = closed;
        paintPin(e);
      }
    }

    const key = shown.map((e) => e.s.id).join();
    if (key !== lastShown) {
      lastShown = key;
      clusterer.clearMarkers(true);
      clusterer.addMarkers(shown.map((e) => e.marker));
    }
    if (shown.length === 0) toast("找不到符合條件的加油站");

    if (fit && state.query && shown.length > 0) {
      mapReady.then(() => {
        if (shown.length === 1) {
          map.setCenter(shown[0].s);
          map.setZoom(15);
        } else {
          const bounds = new google.maps.LatLngBounds();
          shown.forEach(({ s }) => bounds.extend(s));
          map.fitBounds(bounds, { top: topPadding(), bottom: 40, left: 30, right: 30 });
        }
      });
    }
  }

  // ----- search -----
  let searchTimer;
  $("search").addEventListener("input", () => {
    $("search-clear").hidden = !$("search").value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = $("search").value;
      apply({ fit: true });
    }, 300);
  });
  $("search").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
  $("search-clear").addEventListener("click", () => {
    $("search").value = "";
    $("search-clear").hidden = true;
    state.query = "";
    apply();
    fitTaiwan();
  });

  // ----- floating buttons -----
  $("fit").addEventListener("click", fitTaiwan);

  let meMarker = null;
  $("locate").addEventListener("click", () => {
    if (!navigator.geolocation) {
      toast("此瀏覽器不支援定位");
      return;
    }
    toast("定位中…", 10000);
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        $("toast").hidden = true;
        myPos = { lat: coords.latitude, lng: coords.longitude };
        if (!meMarker) {
          meMarker = new AdvancedMarkerElement({ map, content: el("div", { class: "me" }), title: "我的位置", zIndex: 9999 });
        }
        meMarker.position = myPos;
        $("locate").classList.add("on");
        map.panTo(myPos);
        map.setZoom(14);
      },
      () => toast("無法取得位置，請確認已允許定位"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  });

  apply();
  // keep 營業中 and pin colours current
  setInterval(() => apply(), 5 * 60 * 1000);
}

main().catch((err) => {
  console.error(err);
  toast("地圖載入失敗，請稍後再試", 60000);
});
