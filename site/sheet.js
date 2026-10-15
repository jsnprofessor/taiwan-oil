// Station card height, like the Maps apps: it opens at half the screen; drag up for
// nearly full screen, down to go back to half, and down again to close.

const SNAP_PX = 80;   // drag at least this far to change state…
const FLICK = 0.5;    // …or flick at least this fast (px/ms)
const AXIS_PX = 8;    // movement needed before deciding vertical drag vs sideways swipe
const HALF = 0.5;     // share of the screen height
const FULL = 0.92;

/** Where the card settles after a drag. dy and speed are negative when moving up. */
export function nextState(from, dy, speed) {
  const up = dy < -SNAP_PX || speed < -FLICK;
  const down = dy > SNAP_PX || speed > FLICK;
  if (from === "half") return up ? "full" : down ? "closed" : "half";
  return down ? "half" : "full";
}

/**
 * Adds drag handling to a bottom sheet. `onClose` is called when it is dragged closed.
 * Returns { open(), closed() }: call open() after filling the sheet and before showing it,
 * and closed() whenever the sheet is closed some other way.
 */
export function attachSheetDrag(sheet, onClose) {
  const touch = matchMedia("(pointer: coarse)");
  let state = "closed";
  let natural = 0; // the content's own height
  let drag = null;

  const sizes = () => ({
    half: Math.min(natural, Math.round(innerHeight * HALF)),
    full: Math.min(natural, Math.round(innerHeight * FULL)),
  });

  function settle(next) {
    sheet.style.transition = "";
    sheet.style.transform = "";
    if (next === "closed") {
      state = "closed";
      onClose();
      return;
    }
    state = next;
    sheet.style.height = `${sizes()[next]}px`;
    sheet.classList.toggle("full", next === "full"); // content scrolls only when full
  }

  function open() {
    sheet.style.transition = "none";
    sheet.style.height = "auto";
    natural = sheet.offsetHeight;
    // without a touch screen there is nothing to drag: show it all, scrollable
    settle(touch.matches ? "half" : "full");
  }

  sheet.addEventListener("touchstart", (e) => {
    if (state === "closed" || e.touches.length !== 1) return;
    const t = e.touches[0];
    drag = { x: t.clientX, y: t.clientY, h: sheet.offsetHeight, axis: null, lastY: t.clientY, lastT: e.timeStamp, speed: 0 };
  }, { passive: true });

  sheet.addEventListener("touchmove", (e) => {
    if (!drag) return;
    const t = e.touches[0];
    const dx = t.clientX - drag.x;
    const dy = t.clientY - drag.y;
    if (!drag.axis) {
      if (Math.hypot(dx, dy) < AXIS_PX) return;
      drag.axis = Math.abs(dy) > Math.abs(dx) ? "y" : "x"; // "x": photo swipes stay native
      // when full, the content scrolls normally unless pulled down from the very top
      if (drag.axis === "y" && state === "full" && (sheet.scrollTop > 0 || dy < 0)) drag.axis = "scroll";
    }
    if (drag.axis !== "y") return;
    e.preventDefault();
    const { half, full } = sizes();
    const h = drag.h - dy;
    sheet.style.transition = "none";
    if (h >= half) {
      sheet.style.height = `${Math.min(h, full)}px`;
      sheet.style.transform = "";
    } else {
      sheet.style.height = `${half}px`;
      sheet.style.transform = `translateY(${half - h}px)`; // below half: slide down to close
    }
    const dt = e.timeStamp - drag.lastT;
    if (dt > 0) drag.speed = (t.clientY - drag.lastY) / dt;
    drag.lastY = t.clientY;
    drag.lastT = e.timeStamp;
  }, { passive: false });

  const end = () => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (d.axis === "y") settle(nextState(state, d.lastY - d.y, d.speed));
  };
  sheet.addEventListener("touchend", end);
  sheet.addEventListener("touchcancel", end);

  addEventListener("resize", () => { if (state !== "closed") settle(state); });

  return { open, closed: () => { state = "closed"; drag = null; } };
}
