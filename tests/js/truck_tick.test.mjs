// Behaviour tests for one Monster Truck tick, driven through tickTruck with a fake world.
// Spec outcomes (CONTEXT.md, ADRs) are hard-coded; tuning is imported from its owner module.
import { test } from "node:test";
import assert from "node:assert/strict";

import { createTruckState, tickTruck } from "../../behavior_packs/MonsterTruck_BP/scripts/truck_tick.js";
import { DRIVING } from "../../behavior_packs/MonsterTruck_BP/scripts/driving.js";
import { LIQUID_DRAG_RETENTION, SHORELINE_LIFT } from "../../behavior_packs/MonsterTruck_BP/scripts/amphibious.js";
import {
  createFakeDimension,
  createFakeEntity,
  createFakePlayer,
  createFakeTruck,
  createTickInput,
  fixedInput,
} from "./fake_world.mjs";

const GROUND_Y = 61; // top of the stone layer at y = 60

function scene({ riders = [], truckAt = { x: 0.5, y: GROUND_Y, z: 0.5 }, isOnGround = true, driverInput } = {}) {
  const dimension = createFakeDimension();
  dimension.fillLayer(GROUND_Y - 1, "minecraft:stone");
  const truck = createFakeTruck({ location: truckAt, isOnGround, riders });
  // The engine's getEntities around the truck returns the truck itself; it must spare itself.
  dimension.entities.push(truck);
  const input = createTickInput({ driverInput, entities: riders });
  const state = createTruckState();
  let tick = 1000; // system.currentTick in a running world, past the 6-tick trample cooldown
  return {
    dimension,
    truck,
    input,
    state,
    get tick() {
      return tick;
    },
    // Advance one tick; `before` places the truck where the engine moved it.
    step(before) {
      tick += 1;
      before?.(tick);
      tickTruck(truck, dimension, state, input, tick);
      return tick;
    },
  };
}

// Drop the truck from `fromY` to the ground: one still tick, then falling ticks, then landing.
function dropFrom(world, fromY, { mid = [] } = {}) {
  world.step(() => world.truck.moveTo({ y: fromY }, { velocity: { y: 0 }, isOnGround: false }));
  let prev = fromY;
  for (const y of [fromY - 0.5, ...mid]) {
    world.step(() => world.truck.moveTo({ y }, { velocity: { y: y - prev }, isOnGround: false }));
    prev = y;
  }
  return world.step(() => world.truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: true }));
}

test("a drop of 3 or more blocks Crush Stomps mobs beneath and spares players", () => {
  const world = scene();
  const zombie = createFakeEntity({ typeId: "minecraft:zombie", location: { x: 2, y: GROUND_Y, z: 0.5 } });
  const bystander = createFakePlayer({ location: { x: 0.5, y: GROUND_Y, z: -2 } });
  world.dimension.entities.push(zombie, bystander);

  // The drop is measured from where the fall began (the tick before the first falling tick).
  dropFrom(world, GROUND_Y + 3);

  assert.equal(zombie.damage.length, 1, "Crush Stomp hits the mob once");
  assert.ok(zombie.damage[0].amount >= 60, "Crush Stomp is lethal to standard hostiles");
  assert.equal(zombie.damage[0].options.cause, "contact");
  assert.equal(zombie.damage[0].options.damagingEntity, world.truck);
  const push = zombie.impulses[0];
  assert.ok(push.x > 0 && push.y > 0, "radial shockwave pushes outward and up");
  assert.equal(bystander.damage.length, 0, "players are never crushed");
  assert.equal(world.truck.damage.length, 0, "the truck never crushes itself");
  assert.ok(world.dimension.sounds.some((s) => s.soundId === "random.explode"));
});

test("drops under 3 blocks land softly without crushing", () => {
  const world = scene();
  const zombie = createFakeEntity({ location: { x: 2, y: GROUND_Y, z: 0.5 } });
  world.dimension.entities.push(zombie);

  dropFrom(world, GROUND_Y + 2.9);

  assert.equal(zombie.damage.length, 0, "auto-step and curb drops must not crush");
  assert.ok(world.dimension.sounds.some((s) => s.soundId === "random.fizz"), "the landing still vents");
});

test("landing waits for engine ground contact, then vents and raises dust at all four wheels", () => {
  const world = scene();
  world.step(() => world.truck.moveTo({ y: GROUND_Y + 4 }, { isOnGround: false }));
  world.step(() => world.truck.moveTo({ y: GROUND_Y + 3.5 }, { velocity: { y: -0.5 }, isOnGround: false }));
  // Down at ground height but the engine does not report contact yet: still airborne.
  world.step(() => world.truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: false }));
  assert.equal(world.dimension.sounds.length, 0, "no landing before the engine reports ground contact");

  world.step(() => world.truck.moveTo({ y: GROUND_Y }, { isOnGround: true }));
  const vents = world.dimension.sounds.filter((s) => s.soundId === "random.fizz");
  assert.equal(vents.length, 1, "Pneumatic Shock Absorption vents once on landing");
  const dust = world.dimension.particles.filter((p) => p.effectName === "minecraft:campfire_smoke_particle");
  assert.equal(dust.length, 4, "dust at each wheel");
});

test("riders are protected from the drop's fall damage until 8 ticks after landing", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver] });
  world.step(() => world.truck.moveTo({ y: GROUND_Y + 4 }, { isOnGround: false }));
  assert.equal(world.input.protectedRiders.has("driver"), false, "no protection before a drop");

  world.step(() => world.truck.moveTo({ y: GROUND_Y + 3.5 }, { velocity: { y: -0.5 }, isOnGround: false }));
  assert.equal(world.input.protectedRiders.get("driver"), world.truck.id, "the fall start protects the riders");

  const landed = world.step(() => world.truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: true }));
  while (world.tick < landed + 8) {
    world.step();
    assert.ok(world.input.protectedRiders.has("driver"), `still protected at landing + ${world.tick - landed}`);
  }
  world.step();
  assert.equal(world.input.protectedRiders.has("driver"), false, "protection ends with the landing window");
});

// The engine detaches the driver right after landing and refuses to reseat until `refuseUntil`.
// `beforeReseat(driver)` runs on the last refused tick, just before the engine would accept.
function detachAfterLanding(refuseFor, { beforeReseat } = {}) {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver] });
  const landed = dropFrom(world, GROUND_Y + 3);
  const rideable = world.truck.getComponent("minecraft:rideable");
  const reseat = rideable.addRider;
  let refusing = true;
  world.truck.getComponent = () => ({
    getRiders: rideable.getRiders,
    addRider: (rider) => (refusing ? false : reseat(rider)),
  });
  const detachedAt = world.step(() => world.truck.detach(driver));
  while (world.tick < detachedAt + refuseFor) world.step();
  beforeReseat?.(driver);
  refusing = false;
  world.step();
  return { world, driver, landed, detachedAt };
}

test("a rider the engine detaches after landing is reseated within the 8-tick retention window", () => {
  const { world, driver, detachedAt } = detachAfterLanding(7);
  assert.equal(world.tick, detachedAt + 8);
  assert.ok(world.truck.seated.includes(driver), "reseated on the last tick of the window");
});

test("the retention window is bounded: no reseat once it has passed", () => {
  const { world, driver, detachedAt } = detachAfterLanding(8);
  assert.equal(world.tick, detachedAt + 9);
  assert.ok(!world.truck.seated.includes(driver), "no reseat after the window");
  assert.equal(world.input.protectedRiders.has("driver"), false);
});

test("a protected rider who sneaks during the retention window is not pulled back into the seat", () => {
  const { world, driver, detachedAt } = detachAfterLanding(3, {
    beforeReseat: (rider) => {
      rider.isSneaking = true;
    },
  });
  assert.ok(world.tick <= detachedAt + 8, "still inside the retention window");
  assert.ok(!world.truck.seated.includes(driver), "Sneak is a deliberate exit even while the window is open");
});

test("a rider detached on the tick a fall starts is reseated, protected, and the drop still counts", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver] });
  const zombie = createFakeEntity({ location: { x: 2, y: GROUND_Y, z: 0.5 } });
  world.dimension.entities.push(zombie);
  world.step(() => world.truck.moveTo({ y: GROUND_Y + 3 }, { isOnGround: false }));
  world.step(() => {
    world.truck.moveTo({ y: GROUND_Y + 2.5 }, { velocity: { y: -0.5 }, isOnGround: false });
    world.truck.detach(driver);
  });
  assert.ok(world.truck.seated.includes(driver), "the engine detachment is undone");
  assert.equal(world.input.protectedRiders.get("driver"), world.truck.id);
  world.step(() => world.truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: true }));
  assert.equal(zombie.damage.length, 1, "the 3-block drop Crush Stomps");
});

test("a rider detached early in a long drop stays protected for the whole fall, not just 8 ticks", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver] });
  // The engine refuses to reseat the rider for the rest of the drop.
  const rideable = world.truck.getComponent("minecraft:rideable");
  world.truck.getComponent = () => ({ getRiders: rideable.getRiders, addRider: () => false });

  const top = GROUND_Y + 14;
  world.step(() => world.truck.moveTo({ y: top }, { velocity: { y: 0 }, isOnGround: false }));
  world.step(() => world.truck.moveTo({ y: top - 1 }, { velocity: { y: -1 }, isOnGround: false }));
  world.step(() => {
    world.truck.moveTo({ y: top - 2 }, { velocity: { y: -1 }, isOnGround: false });
    world.truck.detach(driver);
  });
  assert.ok(!world.truck.seated.includes(driver), "the engine keeps the rider off");
  for (let y = top - 3; y > GROUND_Y; y--) {
    world.step(() => world.truck.moveTo({ y }, { velocity: { y: -1 }, isOnGround: false }));
    assert.equal(world.input.protectedRiders.get("driver"), world.truck.id, `still protected while falling at y=${y}`);
  }

  const landed = world.step(() => world.truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: true }));
  assert.ok(world.input.protectedRiders.has("driver"), "protected on landing");
  while (world.tick < landed + 8) {
    world.step();
    assert.ok(world.input.protectedRiders.has("driver"), `still protected at landing + ${world.tick - landed}`);
  }
  world.step();
  assert.equal(world.input.protectedRiders.has("driver"), false, "protection ends with the landing window");
});

test("Sneak is the only deliberate exit; over liquid the rider is set down on the roof", () => {
  // Not sneaking: any detachment is undone.
  {
    const rider = createFakePlayer({ id: "rider" });
    const world = scene({ riders: [rider] });
    world.step();
    world.step(() => world.truck.detach(rider));
    assert.ok(world.truck.seated.includes(rider), "engine detachment reseats the rider");
  }
  // Sneaking on land: the rider leaves and loses protection.
  {
    const rider = createFakePlayer({ id: "rider" });
    const world = scene({ riders: [rider] });
    world.step();
    world.input.protectedRiders.set("rider", world.truck.id);
    rider.isSneaking = true;
    world.step(() => world.truck.detach(rider));
    assert.ok(!world.truck.seated.includes(rider));
    assert.equal(rider.teleports.length, 0);
    assert.equal(world.input.protectedRiders.has("rider"), false);
  }
  // Sneaking over water: teleported clear of the liquid.
  {
    const rider = createFakePlayer({ id: "rider" });
    const world = scene({ riders: [rider], isOnGround: false });
    world.dimension.setBlock(0, GROUND_Y, 0, "minecraft:water");
    world.step();
    world.input.protectedRiders.set("rider", world.truck.id);
    rider.isSneaking = true;
    world.step(() => world.truck.detach(rider));
    assert.ok(!world.truck.seated.includes(rider));
    assert.equal(world.input.protectedRiders.has("rider"), false, "a deliberate exit over liquid ends protection");
    assert.equal(rider.teleports.length, 1);
    const { location, options } = rider.teleports[0];
    assert.ok(location.y > GROUND_Y + 2, "set down on the roof, above the liquid");
    assert.ok(Math.abs(location.x - 0.5) < 1e-9 && Math.abs(location.z - (0.5 - 0.8)) < 1e-9, "behind the cab");
    assert.equal(options.dimension, world.dimension);
  }
});

test("liquid propulsion follows the driver's W input and crosses at overland speed", () => {
  for (const [liquid, retention] of [["minecraft:water", LIQUID_DRAG_RETENTION.water], ["minecraft:lava", LIQUID_DRAG_RETENTION.lava]]) {
    const driver = createFakePlayer({ id: "driver" });
    const world = scene({ riders: [driver], isOnGround: false, driverInput: fixedInput({ forward: 1 }) });
    world.dimension.setBlock(0, GROUND_Y, 0, liquid);
    world.step();
    assert.equal(world.truck.impulses.length, 1, `${liquid}: W pushes the floating truck`);
    const push = world.truck.impulses[0];
    assert.equal(push.y, 0);
    assert.ok(Math.abs(push.z - DRIVING.acceleration / retention) < 1e-12, `${liquid}: velocity divided by drag retention`);
  }

  // No throttle, no push; nobody seated, no push even if keys are "held".
  for (const [riders, driverInput] of [[[createFakePlayer()], fixedInput()], [[], fixedInput({ forward: 1 })]]) {
    const world = scene({ riders, isOnGround: false, driverInput });
    world.dimension.setBlock(0, GROUND_Y, 0, "minecraft:water");
    world.step();
    assert.equal(world.truck.impulses.length, 0);
  }
});

// Shoreline Step-Up against a bank whose top is `aboveSurface` blocks above the liquid surface
// (bank height counts above the surface: 0 is flush, 1 and 2 are climbed, 3 is a wall). A small
// engine stands in for Bedrock: it moves the truck by the velocity set last tick, then applies
// drag (the order measured in docs/agents/bedrock-physics.md). The bank face (z = 2) stops the
// truck's 2.25-wide collision box until its bottom clears the top. The truck floats in from
// z = -20 so it meets the bank at speed. verticalRetention 0.1 models lava cutting a lift.
// Options: forward(truck) gives W each tick; deep floats the truck in a second liquid block
// under the surface one; floatY overrides where buoyancy holds it; stuck stops any rise (a
// ceiling), so a lift can never finish.
function shorelineClimb(aboveSurface, {
  verticalRetention = 0.8, ticks = 60, forward = () => 1, deep = false, floatY: floatAt, stuck = false,
} = {}) {
  const driver = createFakePlayer({ id: "driver" });
  const floatY = floatAt ?? (deep ? GROUND_Y - 0.4 : GROUND_Y + 0.6); // inside a water block
  let truck;
  const driverInput = {
    movement: () => ({ x: 0, y: forward(truck) }),
    handbrake: () => false,
  };
  const world = scene({ riders: [driver], truckAt: { x: 0.5, y: floatY, z: -19.5 }, isOnGround: false, driverInput });
  truck = world.truck;
  const stopZ = 2 - 1.125;
  const bottom = deep ? GROUND_Y - 1 : GROUND_Y;
  for (let x = -3; x <= 3; x++) {
    for (let z = -22; z <= 1; z++) {
      for (let y = bottom; y <= GROUND_Y; y++) world.dimension.setBlock(x, y, z, "minecraft:water");
    }
    for (let z = 2; z <= 12; z++) {
      for (let y = bottom; y <= GROUND_Y + aboveSurface; y++) world.dimension.setBlock(x, y, z, "minecraft:dirt");
    }
  }
  const top = GROUND_Y + 1 + aboveSurface;
  const lifts = []; // [tick, y] for every purely vertical impulse (the lift; driving has y 0)
  let seen = 0;
  let velocity = { x: 0, y: 0, z: 0 };
  let peak = truck.location.y;
  let climbedAt;
  let contactAt;
  for (let t = 0; t < ticks; t++) {
    world.step(() => {
      for (const impulse of truck.impulses.slice(seen)) {
        velocity = { x: velocity.x + impulse.x, y: velocity.y + impulse.y, z: velocity.z + impulse.z };
        if (impulse.x === 0 && impulse.z === 0 && impulse.y !== 0) lifts.push([t - 1, impulse.y]);
      }
      seen = truck.impulses.length;
      let { y, z } = truck.location;
      if (stuck) velocity.y = Math.min(velocity.y, 0);
      y += velocity.y;
      if (y >= top - 1e-9 || z > stopZ + 1e-9 || z + velocity.z < stopZ) {
        z += velocity.z;
      } else {
        z = stopZ; // the face holds it below the top
        velocity.z = 0;
        contactAt ??= t;
      }
      const onBank = z > stopZ + 0.05 && y <= top;
      if (onBank) {
        y = top;
        velocity.y = 0;
      }
      velocity.y = velocity.y * verticalRetention - 0.08;
      if (!onBank && y <= floatY) {
        y = floatY; // buoyancy holds it at the surface
        velocity.y = 0;
      }
      peak = Math.max(peak, y);
      if (climbedAt === undefined && onBank) climbedAt = t;
      truck.moveTo({ y, z }, { velocity, isOnGround: onBank });
    });
  }
  return { climbedAt, contactAt, peak: peak - top, truck, top, lifts, floatY };
}

test("Shoreline Step-Up climbs flush, 1- and 2-above banks within a second in water and lava", () => {
  for (const [medium, verticalRetention] of [["water", 0.8], ["lava-like clipping", 0.1]]) {
    for (const aboveSurface of [0, 1, 2]) {
      const { climbedAt, contactAt, peak } = shorelineClimb(aboveSurface, { verticalRetention });
      const label = `${medium}, bank ${aboveSurface} above the surface`;
      const took = climbedAt - (contactAt ?? climbedAt);
      assert.ok(climbedAt !== undefined && took <= 20, `${label}: up on the bank within 20 ticks of contact (contact ${contactAt}, up ${climbedAt})`);
      assert.ok(peak <= 0.5, `${label}: not launched (peak +${peak.toFixed(2)} over the top)`);
    }
  }
});

test("a wall 3 blocks above the liquid surface is not a shoreline", () => {
  const { climbedAt, truck } = shorelineClimb(3, { ticks: 50 });
  assert.equal(climbedAt, undefined);
  assert.ok(truck.impulses.every((i) => i.y <= 0), "no Shoreline Step-Up lift");
});

test("a truck floating deeper than the surface block counts the bank from the surface", () => {
  // Floating in the lower of two water blocks: a bank 2 above the surface is still climbed and
  // a wall 3 above it is still refused.
  const two = shorelineClimb(2, { deep: true });
  assert.ok(two.climbedAt !== undefined, "bank 2 above the surface climbed from deeper water");
  const three = shorelineClimb(3, { deep: true, ticks: 50 });
  assert.equal(three.climbedAt, undefined, "wall 3 above the surface refused from deeper water");
  assert.equal(three.lifts.length, 0, "no lift against the wall");
  // Floating right at the surface (the truck's block is air above the water): no lift either.
  const atSurface = shorelineClimb(3, { floatY: GROUND_Y + 1, ticks: 50 });
  assert.equal(atSurface.climbedAt, undefined);
  assert.equal(atSurface.lifts.length, 0, "no lift against the wall from the surface");
});

test("releasing W mid-lift cancels the remaining climb", () => {
  let released = false;
  const result = shorelineClimb(2, {
    forward: (truck) => {
      if (truck.location.y >= GROUND_Y + 1.5) released = true;
      return released ? 0 : 1;
    },
  });
  const releaseLift = result.lifts.findIndex(([, y]) => y < 0);
  assert.ok(released && releaseLift >= 0, "a downward impulse cancels the lift on release");
  assert.ok(result.lifts.slice(releaseLift + 1).every(([, y]) => y <= 0), "no lift after release");
  assert.ok(result.peak < -0.4, `the truck does not keep climbing onto the bank (peak ${result.peak.toFixed(2)} vs top)`);
});

test("a lift that cannot finish gives up until W is pressed again", () => {
  const { maxTicks } = SHORELINE_LIFT;
  let tick = 0;
  // Hold W into a bank the truck cannot rise beside, release for one tick, then press again.
  const result = shorelineClimb(2, {
    stuck: true,
    ticks: 90,
    forward: () => (tick++ === 75 ? 0 : 1),
  });
  const ups = result.lifts.filter(([, y]) => y > 0).map(([t]) => t);
  const first = ups[0];
  assert.ok(first !== undefined, "the lift starts at the bank");
  const beforeRelease = ups.filter((t) => t < 75);
  assert.ok(beforeRelease.every((t) => t < first + maxTicks), `gave up after ${maxTicks} ticks: lifts at ${beforeRelease}`);
  assert.ok(ups.some((t) => t > 75), "pressing W again restarts the lift");
});

test("holding Jump is the handbrake and never launches the truck", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver], driverInput: fixedInput({ handbrake: true }) });
  for (let i = 0; i < 5; i++) world.step();
  assert.ok(world.truck.impulses.length > 0, "a held handbrake holds the parked truck");
  assert.ok(world.truck.impulses.every((i) => i.y === 0), "no Suspension Jump (ADR-0017)");
});

test("Tire Trample damage scales with speed and hits a mob once per cooldown", () => {
  const hit = (speed) => {
    const world = scene();
    const zombie = createFakeEntity({ location: { x: 0.5, y: GROUND_Y, z: 3 } });
    world.dimension.entities.push(zombie);
    world.step(() => world.truck.moveTo({}, { velocity: { z: speed } }));
    world.step(() => world.truck.moveTo({}, { velocity: { z: speed } }));
    return { zombie, world };
  };
  assert.equal(hit(0.05).zombie.damage.length, 0, "a crawling truck does not trample");
  const slow = hit(0.2).zombie;
  const { zombie: fast, world } = hit(0.5);
  assert.equal(fast.damage.length, 1, "one hit within the cooldown");
  assert.ok(fast.damage[0].amount > slow.damage[0].amount, "faster hits harder");
  assert.equal(fast.damage[0].options.cause, "entityAttack");
  assert.equal(fast.damage[0].options.damagingEntity, world.truck);
  assert.ok(fast.impulses[0].z > 0, "knocked away from the truck");
  assert.equal(world.truck.damage.length, 0, "the truck never tramples itself");
});

test("the trample cooldown is 6 ticks: no repeat hit at +5, a fresh hit at +6", () => {
  const world = scene();
  const zombie = createFakeEntity({ location: { x: 0.5, y: GROUND_Y, z: 3 } });
  world.dimension.entities.push(zombie);
  const roll = () => world.step(() => world.truck.moveTo({}, { velocity: { z: 0.5 } }));
  let firstHit;
  for (let i = 0; i < 3 && firstHit === undefined; i++) {
    const t = roll();
    if (zombie.damage.length === 1) firstHit = t;
  }
  assert.notEqual(firstHit, undefined, "the rolling truck tramples the mob");
  while (world.tick < firstHit + 5) {
    roll();
    assert.equal(zombie.damage.length, 1, `still cooling down at +${world.tick - firstHit}`);
  }
  roll();
  assert.equal(zombie.damage.length, 2, "hit again once 6 ticks have passed");
});

test("the trample cooldown is per truck: a second truck still hits a mob the first just hit", () => {
  const world = scene();
  const other = createFakeTruck({ location: { x: 0.5, y: GROUND_Y, z: 5.5 } });
  const otherState = createTruckState();
  world.dimension.entities.push(other);
  const zombie = createFakeEntity({ location: { x: 0.5, y: GROUND_Y, z: 3 } });
  world.dimension.entities.push(zombie);

  const tick = world.step(() => world.truck.moveTo({}, { velocity: { z: 0.5 } }));
  assert.equal(zombie.damage.length, 1, "truck A tramples the mob");
  other.moveTo({}, { velocity: { z: -0.5 } });
  tickTruck(other, world.dimension, otherState, world.input, tick);
  assert.equal(zombie.damage.length, 2, "truck B is not shielded by truck A's cooldown");
  assert.equal(zombie.damage[1].options.damagingEntity, other);

  world.step(() => world.truck.moveTo({}, { velocity: { z: 0.5 } }));
  assert.equal(zombie.damage.length, 2, "truck A is still cooling down on that mob");
});

test("a heavy collision that halts the truck leaves the next tick's measured motion true", () => {
  const world = scene();
  const golem = createFakeEntity({ typeId: "minecraft:iron_golem", location: { x: 0.5, y: GROUND_Y, z: 3 } });
  world.dimension.entities.push(golem);
  world.step(() => world.truck.moveTo({}, { velocity: { z: 0.2 } }));
  assert.equal(world.truck.cleared, 1, "the slow hit on the golem halts the truck");

  // Next tick the truck has moved 0.5 blocks; the halt must leave prevX/Y/Z alone so dz reports
  // it. (The pre-refactor re-store wrote the tick-start location, already stored, so it was a
  // no-op: this guards motion measurement against writes from the halt, not a past regression.)
  const zombie = createFakeEntity({ location: { x: 0.5, y: GROUND_Y, z: 3.5 } });
  world.dimension.entities.push(zombie);
  world.step(() => world.truck.moveTo({ z: 1 }, { velocity: { z: 0 } }));
  assert.equal(zombie.damage.length, 1);
  assert.equal(zombie.damage[0].amount, 60, "trample speed is the true 0.5 blocks/tick moved (0.5 * 120)");
});

test("lava shields riders from burning and ignites mobs trampled after leaving it", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver], isOnGround: false });
  world.dimension.setBlock(0, GROUND_Y, 0, "minecraft:lava");
  world.step();
  assert.equal(driver.extinguished, 1, "riders are extinguished while in lava");

  world.dimension.setBlock(0, GROUND_Y, 0, "minecraft:air");
  const zombie = createFakeEntity({ location: { x: 0.5, y: GROUND_Y, z: 3 } });
  world.dimension.entities.push(zombie);
  world.step(() => world.truck.moveTo({}, { velocity: { z: 0.5 }, isOnGround: true }));
  assert.equal(zombie.fire.length, 1, "Molten Tire Trample sets the mob on fire");
});

test("wood demolition needs momentum over 0.25 blocks/tick; foliage shears at any speed with a driver", () => {
  const run = (speed, riders) => {
    const world = scene({ riders });
    world.dimension.setBlock(0, GROUND_Y, 2, "minecraft:oak_planks");
    world.dimension.setBlock(0, GROUND_Y + 3, 2, "minecraft:oak_planks"); // above the 3-block wood band
    world.dimension.setBlock(1, GROUND_Y + 1, 1, "minecraft:oak_leaves");
    world.step(() => world.truck.moveTo({}, { velocity: { z: speed } }));
    return world.dimension;
  };
  const slow = run(0.2, [createFakePlayer()]);
  assert.equal(slow.commands.length, 0, "0.2 blocks/tick does not break wood");
  assert.equal(slow.typeAt(1, GROUND_Y + 1, 1), "minecraft:air", "foliage shears while slow");

  const fast = run(0.3, [createFakePlayer()]);
  assert.deepEqual(fast.commands, [`setblock 0 ${GROUND_Y} 2 air destroy`], "wood breaks with survival drops");
  assert.equal(fast.typeAt(0, GROUND_Y + 3, 2), "minecraft:oak_planks");

  const empty = run(0.2, []);
  assert.equal(empty.typeAt(1, GROUND_Y + 1, 1), "minecraft:oak_leaves", "no shearing without a driver");
});

test("the truck owns its yaw and shows steering and pitch on its properties", () => {
  const driver = createFakePlayer({ id: "driver" });
  const world = scene({ riders: [driver], driverInput: fixedInput({ strafe: 1 }) });
  world.step();
  assert.deepEqual(world.truck.rotation, { x: 0, y: 0 }, "a parked truck does not spin");
  assert.equal(world.truck.properties["blake:steer_angle"], -DRIVING.steerRate, "A turns the wheels left");
  assert.equal(world.truck.properties["blake:pitch_angle"], 0, "level on flat ground");
});
