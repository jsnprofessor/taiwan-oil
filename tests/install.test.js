import { test } from "node:test";
import assert from "node:assert/strict";
import { installPlatform, bannerDue, DISMISS_DAYS } from "../site/install.js";

const UA = {
  iphoneSafari: "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
  iphoneChrome: "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/141.0.0.0 Mobile/15E148 Safari/604.1",
  // iPadOS Safari asks for desktop sites, so it looks like a Mac
  ipadAsMac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
  mac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15",
  androidChrome: "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
  windows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
};
const env = (ua, o = {}) => ({ ua, standalone: false, maxTouchPoints: 0, ...o });

test("iPhone browsers that can add to the home screen get the iOS steps", () => {
  assert.equal(installPlatform(env(UA.iphoneSafari, { maxTouchPoints: 5 })), "ios");
  assert.equal(installPlatform(env(UA.iphoneChrome, { maxTouchPoints: 5 })), "ios");
});

test("an iPad that reports itself as a Mac is still iOS", () => {
  assert.equal(installPlatform(env(UA.ipadAsMac, { maxTouchPoints: 5 })), "ios");
  assert.equal(installPlatform(env(UA.mac, { maxTouchPoints: 0 })), null);
});

test("Android Chrome is android; desktops get nothing", () => {
  assert.equal(installPlatform(env(UA.androidChrome, { maxTouchPoints: 5 })), "android");
  assert.equal(installPlatform(env(UA.windows)), null);
});

test("already opened from the home screen means nothing to offer", () => {
  assert.equal(installPlatform(env(UA.iphoneSafari, { standalone: true, maxTouchPoints: 5 })), "installed");
  assert.equal(installPlatform(env(UA.androidChrome, { standalone: true, maxTouchPoints: 5 })), "installed");
});

test("the banner comes back only after the dismiss period", () => {
  const now = Date.UTC(2026, 9, 15);
  const day = 24 * 60 * 60 * 1000;
  assert.equal(bannerDue(null, now), true);
  assert.equal(bannerDue("not a number", now), true);
  assert.equal(bannerDue(String(now - day), now), false);
  assert.equal(bannerDue(String(now - (DISMISS_DAYS - 1) * day), now), false);
  assert.equal(bannerDue(String(now - DISMISS_DAYS * day), now), true);
});
