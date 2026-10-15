// "Add to home screen" decisions. Pure functions so they can be tested in Node.

export const DISMISS_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * What kind of add-to-home-screen help fits this browser.
 * @param {{ua: string, standalone: boolean, maxTouchPoints: number}} env
 * @returns {"installed"|"ios"|"android"|null}
 *   null means a desktop, where we offer nothing.
 */
export function installPlatform({ ua, standalone, maxTouchPoints }) {
  if (standalone) return "installed";
  // iPadOS Safari reports itself as a Mac; a touch screen gives it away
  const ios = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouchPoints > 1);
  if (ios) return "ios";
  if (/Android/.test(ua)) return "android";
  return null;
}

/** Whether to show the banner, given the stored dismiss time (ms since epoch, as a string). */
export function bannerDue(dismissedAt, now = Date.now()) {
  const t = Number(dismissedAt);
  return !dismissedAt || !Number.isFinite(t) || now - t >= DISMISS_DAYS * DAY_MS;
}
