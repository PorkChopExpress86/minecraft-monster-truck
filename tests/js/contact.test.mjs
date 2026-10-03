// Behaviour tests for contact.js: what the truck's tires and bumper do to the entities they
// touch (Tire Trample, Molten Tire Trample, heavy collisions, the hit cooldown), driven through
// stepContact with a fake world. Spec outcomes (CONTEXT.md, ADR-0008) are hard-coded.
import { test } from "node:test";
import assert from "node:assert/strict";

import { stepContact } from "../../behavior_packs/MonsterTruck_BP/scripts/contact.js";
import { createFakeDimension, createFakeEntity, createFakeTruck } from "./fake_world.mjs";

const AT = { x: 0.5, y: 61, z: 0.5 };
const AHEAD = { x: 0.5, y: 61, z: 3 }; // in front of a truck heading +Z

function scene(targetType = "minecraft:zombie") {
  const dimension = createFakeDimension();
  const truck = createFakeTruck({ location: AT });
  const target = createFakeEntity({ typeId: targetType, location: AHEAD });
  dimension.entities.push(truck, target);
  const hitCooldowns = new Map();
  const contact = (speed, { tick = 1000, moltenUntil } = {}) =>
    stepContact(truck, dimension, { location: AT, heading: { x: 0, z: 1 }, speed, moltenUntil, hitCooldowns, tick });
  return { truck, target, hitCooldowns, contact };
}

test("a hit the engine rejects with damage options still lands as a plain hit", () => {
  const { target, contact } = scene();
  target.applyDamage = (amount, options) => {
    if (options) throw new Error("damagingEntity not accepted");
    target.damage.push({ amount, options });
    return true;
  };
  contact(0.5);
  assert.deepEqual(target.damage, [{ amount: 60, options: undefined }]);
});

test("a heavy entity hit at 0.32 blocks/tick or less stops the truck dead", () => {
  const { truck, target, contact } = scene("minecraft:iron_golem");
  contact(0.2);
  assert.equal(truck.cleared, 1, "the truck's velocity is cleared");
  assert.equal(truck.impulses.length, 1);
  assert.ok(truck.impulses[0].z < 0, "and nudged back off the golem");
  assert.equal(target.impulses.length, 0, "the golem is not shoved");
  assert.equal(target.damage.length, 1);
});

test("a heavy entity hit above 0.32 blocks/tick is shoved through with heavy damage", () => {
  const { truck, target, contact } = scene("minecraft:warden");
  contact(0.4);
  assert.equal(truck.cleared, 0);
  assert.ok(target.impulses[0].z > 0, "the target is shoved forward");
  assert.ok(truck.impulses[0].z < 0, "the truck loses some speed");
  assert.ok(target.damage[0].amount >= 50);
  assert.equal(target.damage[0].options.cause, "entityAttack");
  assert.equal(target.damage[0].options.damagingEntity, truck);
});

test("Molten Tire Trample ignites only before moltenUntil, for heavy and regular targets", () => {
  for (const type of ["minecraft:zombie", "minecraft:iron_golem"]) {
    const burning = scene(type);
    burning.contact(0.5, { tick: 1000, moltenUntil: 1001 });
    assert.deepEqual(burning.target.fire, [{ seconds: 6, useEffects: true }], `${type} burns`);

    const cooled = scene(type);
    cooled.contact(0.5, { tick: 1001, moltenUntil: 1001 });
    assert.equal(cooled.target.fire.length, 0, `${type}: the tires have cooled`);
  }
});

test("the hit cooldown is shared through the map it is given", () => {
  const { target, hitCooldowns, contact } = scene();
  contact(0.5, { tick: 1000 });
  assert.equal(hitCooldowns.get(target.id), 1000);
  contact(0.5, { tick: 1005 });
  assert.equal(target.damage.length, 1, "cooling down at +5");
  contact(0.5, { tick: 1006 });
  assert.equal(target.damage.length, 2, "hit again at +6");
});

test("expired cooldowns are pruned, even on a tick the truck is too slow to trample", () => {
  const { target, hitCooldowns, contact } = scene();
  contact(0.5, { tick: 1000 });
  contact(0, { tick: 1005 });
  assert.equal(hitCooldowns.get(target.id), 1000, "still cooling down at +5");
  contact(0, { tick: 1006 });
  assert.equal(hitCooldowns.size, 0, "expired at +6 and forgotten");
});

test("an entity that throws when read does not spare the entities after it", () => {
  const { truck, target } = scene();
  const broken = createFakeEntity({ location: AHEAD });
  Object.defineProperty(broken, "typeId", { get() { throw new Error("entity is no longer valid"); } });
  const dimension = createFakeDimension();
  dimension.entities.push(truck, broken, target);
  stepContact(truck, dimension, { location: AT, heading: { x: 0, z: 1 }, speed: 0.5, hitCooldowns: new Map(), tick: 1000 });
  assert.equal(target.damage.length, 1, "the next entity is still trampled");
});
