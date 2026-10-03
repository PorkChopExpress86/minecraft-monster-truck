// Behaviour tests for landing.js: the drop lifecycle (free fall, rider protection, Pneumatic
// Shock Absorption, Crush Stomp) driven through stepLanding, and the fall-damage rule the
// entityHurt handler in main.js asks about. The full lifecycle across ticks is covered through
// tickTruck in truck_tick.test.mjs. Spec outcomes (CONTEXT.md, ADR-0017) are hard-coded.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  absorbsFallDamage,
  createLandingState,
  stepLanding,
} from "../../behavior_packs/MonsterTruck_BP/scripts/landing.js";
import { createFakeDimension, createFakeEntity, createFakePlayer, createFakeTruck } from "./fake_world.mjs";

const GROUND_Y = 61;

function frame(world, overrides = {}) {
  return {
    location: world.truck.location,
    dy: 0,
    verticalVelocity: 0,
    heading: { x: 0, z: 1 },
    rideable: world.truck.getComponent("minecraft:rideable"),
    riderIds: world.truck.seated.map((rider) => rider.id),
    prevRiderIds: world.truck.seated.map((rider) => rider.id),
    inLiquid: false,
    tick: 1000,
    getEntity: (id) => world.truck.seated.find((rider) => rider.id === id),
    protectedRiders: world.protectedRiders,
    ...overrides,
  };
}

function scene({ riders = [], y = GROUND_Y, isOnGround = true } = {}) {
  const dimension = createFakeDimension();
  const truck = createFakeTruck({ location: { x: 0.5, y, z: 0.5 }, isOnGround, riders });
  dimension.entities.push(truck);
  return { dimension, truck, landing: createLandingState(), protectedRiders: new Map() };
}

test("fall damage is absorbed for the truck and its protected riders only", () => {
  const truck = createFakeTruck();
  const rider = createFakePlayer({ id: "rider" });
  const walker = createFakePlayer({ id: "walker" });
  const protectedRiders = new Map([["rider", truck.id]]);
  assert.equal(absorbsFallDamage("fall", truck, protectedRiders), true);
  assert.equal(absorbsFallDamage("damage.fall", truck, protectedRiders), true, "Bedrock fall cause string");
  assert.equal(absorbsFallDamage("fall", rider, protectedRiders), true);
  assert.equal(absorbsFallDamage("entityAttack", truck, protectedRiders), false, "combat is not a fall");
  assert.equal(absorbsFallDamage("fall", walker, protectedRiders), false, "a player outside the drop takes fall damage");
  assert.equal(absorbsFallDamage("fall", createFakeEntity(), protectedRiders), false);
  assert.equal(absorbsFallDamage("fall", undefined, protectedRiders), false);
});

test("a level truck is not falling and makes no landing", () => {
  const world = scene();
  assert.equal(world.landing.isFalling, false);
  stepLanding(world.truck, world.dimension, world.landing, frame(world));
  assert.equal(world.landing.isFalling, false);
  assert.equal(world.dimension.sounds.length, 0);
});

test("a fall start remembers where the drop began and protects the seated riders", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver], y: GROUND_Y + 2.5, isOnGround: false });
  stepLanding(world.truck, world.dimension, world.landing, frame(world, { dy: -0.5, verticalVelocity: -0.5 }));
  assert.equal(world.landing.isFalling, true);
  assert.equal(world.landing.fallStartY, GROUND_Y + 3);
  assert.equal(world.protectedRiders.get("driver"), world.truck.id);
});

test("a Crush Stomp the engine rejects with damage options still lands as a plain hit", () => {
  const world = scene();
  const zombie = createFakeEntity({ location: { x: 2, y: GROUND_Y, z: 0.5 } });
  zombie.applyDamage = (amount, options) => {
    if (options) throw new Error("damagingEntity not accepted");
    zombie.damage.push({ amount, options });
    return true;
  };
  world.dimension.entities.push(zombie);
  world.landing.isFalling = true;
  world.landing.fallStartY = GROUND_Y + 3;
  stepLanding(world.truck, world.dimension, world.landing, frame(world, { dy: -0.5 }));
  assert.equal(world.landing.isFalling, false, "landed");
  assert.equal(zombie.damage.length, 1);
  assert.ok(zombie.damage[0].amount >= 60);
  assert.equal(zombie.damage[0].options, undefined);
});

function crushStompScene() {
  const world = scene();
  world.landing.isFalling = true;
  world.landing.fallStartY = GROUND_Y + 3;
  return world;
}

test("an entity that throws when read does not spare the others from a Crush Stomp", () => {
  const world = crushStompScene();
  const broken = createFakeEntity({ location: { x: 1, y: GROUND_Y, z: 0.5 } });
  Object.defineProperty(broken, "typeId", { get() { throw new Error("entity is no longer valid"); } });
  const zombie = createFakeEntity({ location: { x: 2, y: GROUND_Y, z: 0.5 } });
  world.dimension.entities.push(broken, zombie);
  stepLanding(world.truck, world.dimension, world.landing, frame(world, { dy: -0.5 }));
  assert.equal(zombie.damage.length, 1, "the zombie is still crushed");
  assert.ok(world.dimension.sounds.some((sound) => sound.soundId === "random.explode"), "the stomp is still heard");
  assert.ok(world.dimension.particles.some((p) => p.effectName === "minecraft:large_explosion"), "and seen");
});

test("a Crush Stomp whose entity query fails still sounds and shows the explosion", () => {
  const world = crushStompScene();
  world.dimension.getEntities = () => { throw new Error("query rejected"); };
  stepLanding(world.truck, world.dimension, world.landing, frame(world, { dy: -0.5 }));
  assert.ok(world.dimension.sounds.some((sound) => sound.soundId === "random.explode"));
  assert.ok(world.dimension.particles.some((p) => p.effectName === "minecraft:large_explosion"));
});
