// Behaviour tests for durability.js: what a hit costs the truck's Durability and the one-row heart gauge
// that shows it (ADR-0020). The hurt handler that applies them is tested in main.test.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DURABILITY,
  GAUGE_HEALTH,
  IMMUNITY_TICKS,
  gaugeHealth,
  hitCost,
} from "../../behavior_packs/MonsterTruck_BP/scripts/durability.js";

test("a fresh truck absorbs 1000 points and shows them as one row of 10 hearts", () => {
  assert.equal(DURABILITY, 1000);
  assert.equal(GAUGE_HEALTH, 20);
  assert.equal(gaugeHealth(DURABILITY), 20);
});

test("combat, projectiles and explosions cost a quarter of their damage; heat and the rest cost all of it", () => {
  for (const cause of ["entityAttack", "projectile", "entityExplosion", "blockExplosion"]) {
    assert.equal(hitCost({}, cause, 40, 0), 10, cause);
  }
  for (const cause of ["fire", "fireTick", "lava", "lightning", "magic"]) {
    assert.equal(hitCost({}, cause, 40, 0), 40, cause);
  }
});

test("fall damage never costs Durability", () => {
  assert.equal(hitCost({}, "fall", 40, 0), 0);
});

test("a hit inside the immunity window costs only what it exceeds the last hit by", () => {
  const state = {};
  assert.equal(hitCost(state, "fire", 8, 100), 8);
  assert.equal(hitCost(state, "fire", 8, 101), 0, "lava and burning hit every tick but cost once per window");
  assert.equal(hitCost(state, "fire", 12, 105), 4);
  assert.equal(hitCost(state, "fire", 12, 100 + IMMUNITY_TICKS - 1), 0, "the window runs from the first hit");
  assert.equal(hitCost(state, "fire", 12, 100 + IMMUNITY_TICKS), 12);
});

test("a hit that costs nothing does not open an immunity window", () => {
  const state = {};
  assert.equal(hitCost(state, "fall", 40, 100), 0);
  assert.equal(hitCost(state, "lava", 4, 101), 4);
});

test("the gauge shows the share of Durability left, never fewer than half a heart while the truck stands", () => {
  assert.equal(gaugeHealth(910), 19);
  assert.equal(gaugeHealth(501), 11);
  assert.equal(gaugeHealth(500), 10);
  assert.equal(gaugeHealth(1), 1);
});
