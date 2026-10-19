// Behaviour tests for landing.js: the drop lifecycle (free fall, rider protection, Pneumatic
// Shock Absorption, Crush Stomp) driven through stepLanding, and the fall-damage rule the
// entityHurt handler in main.js asks about. The full lifecycle across ticks is covered through
// tickTruck in truck_tick.test.mjs. Spec outcomes (CONTEXT.md, ADR-0017) are hard-coded.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  absorbsFallDamage,
  createLandingState,
  findDoorLanding,
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
    facing: { x: 0, z: 1 },
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

// Door-side dismount (findDoorLanding): a truck at (10, 61, 10) on flat stone. Facing +Z (South) the
// driver's door is on its left (+X) and the passenger's on its right (-X); the rider is set down beside
// the cab, 0.15 ahead of the truck's middle. Positions are rounded so float noise does not hide the diff.
const SOUTH = { x: 0, z: 1 };
const DOOR_Z = 10.15;
const at6 = (p) => ({ x: +p.x.toFixed(6), y: +p.y.toFixed(6), z: +p.z.toFixed(6) });

function doorWorld() {
  const dimension = createFakeDimension();
  dimension.fillLayer(GROUND_Y - 1, "minecraft:stone", 10, 10, 6);
  return dimension;
}

// Two blocks of stone where a rider's feet and head would go: no footing in that column.
function wall(dimension, x, z = 10) {
  dimension.setBlock(x, GROUND_Y, z, "minecraft:stone");
  dimension.setBlock(x, GROUND_Y + 1, z, "minecraft:stone");
}

test("on open ground the driver is set down 1.8 blocks out of the left door, the passenger out of the right", () => {
  const dimension = doorWorld();
  const loc = { x: 10, y: GROUND_Y, z: 10 };
  assert.deepEqual(at6(findDoorLanding(dimension, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y, z: DOOR_Z });
  assert.deepEqual(at6(findDoorLanding(dimension, loc, SOUTH, true)), { x: 8.2, y: GROUND_Y, z: DOOR_Z });
  // Facing +X (East) the driver's left is -Z.
  assert.deepEqual(at6(findDoorLanding(dimension, loc, { x: 1, z: 0 }, false)), { x: 10.15, y: GROUND_Y, z: 8.2 });
});

test("a blocked spot outside the door sets the rider down 1.5 blocks out, then 2.2", () => {
  const dimension = doorWorld();
  // From x 10.375, 1.8 out is column 12 and 1.5 out is column 11.
  wall(dimension, 12);
  assert.deepEqual(at6(findDoorLanding(dimension, { x: 10.375, y: GROUND_Y, z: 10 }, SOUTH, false)),
    { x: 11.875, y: GROUND_Y, z: DOOR_Z }, "1.8 blocked: 1.5 out");

  const nearBlocked = doorWorld();
  // From x 10, 1.5 and 1.8 out are both column 11 and 2.2 out is column 12.
  wall(nearBlocked, 11);
  assert.deepEqual(at6(findDoorLanding(nearBlocked, { x: 10, y: GROUND_Y, z: 10 }, SOUTH, false)),
    { x: 12.2, y: GROUND_Y, z: DOOR_Z }, "1.8 and 1.5 blocked: 2.2 out");
});

test("with its own door side walled in, a rider is set down out of the other side", () => {
  const loc = { x: 10, y: GROUND_Y, z: 10 };
  const driverSideWalled = doorWorld();
  wall(driverSideWalled, 11);
  wall(driverSideWalled, 12);
  assert.deepEqual(at6(findDoorLanding(driverSideWalled, loc, SOUTH, false)), { x: 8.2, y: GROUND_Y, z: DOOR_Z });

  const passengerSideWalled = doorWorld();
  wall(passengerSideWalled, 8);
  wall(passengerSideWalled, 7);
  assert.deepEqual(at6(findDoorLanding(passengerSideWalled, loc, SOUTH, true)), { x: 11.8, y: GROUND_Y, z: DOOR_Z });
});

test("outside the door the rider stands one block up a step, or one or two blocks down a dip, step first", () => {
  const loc = { x: 10, y: GROUND_Y, z: 10 };
  const step = doorWorld();
  step.setBlock(11, GROUND_Y, 10, "minecraft:stone");
  assert.deepEqual(at6(findDoorLanding(step, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y + 1, z: DOOR_Z }, "up a step");

  const dip = doorWorld();
  dip.setBlock(11, GROUND_Y - 1, 10, "minecraft:air");
  dip.setBlock(11, GROUND_Y - 2, 10, "minecraft:stone");
  assert.deepEqual(at6(findDoorLanding(dip, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y - 1, z: DOOR_Z }, "down one");

  const deepDip = doorWorld();
  deepDip.setBlock(11, GROUND_Y - 1, 10, "minecraft:air");
  deepDip.setBlock(11, GROUND_Y - 3, 10, "minecraft:stone");
  assert.deepEqual(at6(findDoorLanding(deepDip, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y - 2, z: DOOR_Z }, "down two");

  // A block at foot height over a two-deep hole offers both; the step up wins.
  const both = doorWorld();
  both.setBlock(11, GROUND_Y, 10, "minecraft:stone");
  both.setBlock(11, GROUND_Y - 1, 10, "minecraft:air");
  both.setBlock(11, GROUND_Y - 3, 10, "minecraft:stone");
  assert.deepEqual(at6(findDoorLanding(both, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y + 1, z: DOOR_Z }, "step before dip");
});

test("with no block lookup the rider is set down 1.8 blocks out of their own door at the truck's height", () => {
  const loc = { x: 10, y: GROUND_Y + 0.4, z: 10 };
  for (const dimension of [undefined, {}]) {
    assert.deepEqual(at6(findDoorLanding(dimension, loc, SOUTH, false)), { x: 11.8, y: GROUND_Y + 0.4, z: DOOR_Z });
    assert.deepEqual(at6(findDoorLanding(dimension, loc, SOUTH, true)), { x: 8.2, y: GROUND_Y + 0.4, z: DOOR_Z });
  }
});

test("a rider who leaves on steady ground is set down outside the door of the seat they left", () => {
  for (const [seat, expectedX] of [[0, 2.3], [1, -1.3]]) {
    const riders = [createFakePlayer({ id: "driver" }), createFakePlayer({ id: "passenger" })];
    const world = scene({ riders });
    world.dimension.fillLayer(GROUND_Y - 1, "minecraft:stone");
    const leaving = riders[seat];
    world.truck.detach(leaving);
    stepLanding(world.truck, world.dimension, world.landing, frame(world, {
      prevRiderIds: ["driver", "passenger"],
      getEntity: (id) => riders.find((rider) => rider.id === id),
    }));
    assert.equal(leaving.teleports.length, 1, `seat ${seat}: set down once`);
    assert.deepEqual(at6(leaving.teleports[0].location), { x: expectedX, y: GROUND_Y, z: 0.65 }, `seat ${seat}`);
    assert.equal(leaving.teleports[0].options.dimension, world.dimension);
    assert.equal(riders[1 - seat].teleports.length, 0, "the rider still seated stays put");
  }
});

// Only a rider the engine set down beside the seat is moved to the door. One who left by /tp, an ender
// pearl, chorus fruit or a portal is where they went, in whatever dimension, and stays there. BDS run
// bd5d8c33: an ejected rider stands 0.96 blocks from the truck's middle (0.45, 0, -0.85) when parked and
// 1.15 at top speed; a teleported one is at the destination, and the 1.0.14 candidate pulled them back.
test("a rider who left to somewhere far from the truck, or to another dimension, stays there; one beside the seat goes to the door", () => {
  const cases = [
    ["beside the seat", { x: 0.95, y: GROUND_Y, z: -0.35 }, "minecraft:overworld", [{ x: 2.3, y: GROUND_Y, z: 0.65 }]],
    ["30 blocks away", { x: 0.5, y: GROUND_Y, z: 30.5 }, "minecraft:overworld", []],
    ["in the nether", { x: 0.5, y: GROUND_Y + 1, z: 0.5 }, "minecraft:nether", []],
  ];
  for (const [label, location, dimensionId, expected] of cases) {
    const rider = createFakePlayer({ id: "rider" });
    const world = scene({ riders: [rider] });
    world.dimension.fillLayer(GROUND_Y - 1, "minecraft:stone");
    world.truck.detach(rider);
    rider.location = location;
    rider.dimension = { id: dimensionId };
    world.protectedRiders.set("rider", world.truck.id);
    stepLanding(world.truck, world.dimension, world.landing, frame(world, { prevRiderIds: ["rider"], getEntity: () => rider }));
    assert.deepEqual(rider.teleports.map((t) => at6(t.location)), expected, label);
    assert.equal(world.protectedRiders.has("rider"), false, `${label}: protection ends with the exit`);
  }
});

