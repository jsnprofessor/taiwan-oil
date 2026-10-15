import { test } from "node:test";
import assert from "node:assert/strict";
import { nextState } from "../site/sheet.js";

// dy: finger movement in px (negative = up); speed: px/ms at release (negative = up)

test("from half: a small drag stays at half", () => {
  assert.equal(nextState("half", -30, 0), "half");
  assert.equal(nextState("half", 30, 0), "half");
});

test("from half: drag or flick up expands, down closes", () => {
  assert.equal(nextState("half", -120, 0), "full");
  assert.equal(nextState("half", -20, -0.8), "full");
  assert.equal(nextState("half", 120, 0), "closed");
  assert.equal(nextState("half", 20, 0.8), "closed");
});

test("from full: drag or flick down returns to half, never straight to closed", () => {
  assert.equal(nextState("full", 30, 0), "full");
  assert.equal(nextState("full", 120, 0), "half");
  assert.equal(nextState("full", 400, 2), "half");
  assert.equal(nextState("full", 20, 0.8), "half");
  assert.equal(nextState("full", -120, -1), "full");
});

test("sheets without a half step: drag or flick down closes, anything else stays", () => {
  assert.equal(nextState("full", 120, 0, false), "closed");
  assert.equal(nextState("full", 20, 0.8, false), "closed");
  assert.equal(nextState("full", 30, 0, false), "full");
  assert.equal(nextState("full", -120, -1, false), "full");
});
