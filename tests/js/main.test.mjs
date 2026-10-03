// Behaviour tests for main.js: the driverInput seam, what it subscribes to, its tick loop, and
// the before-hurt rules (Pneumatic Shock Absorption, thermal shielding, Vehicle Item retrieval).
// main.js is loaded against the fake @minecraft/server in fake_server.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";

import { ButtonState, InputButton, ItemStack, fake, hurt, runTick } from "./fake_server.mjs";
import { createFakeDimension, createFakeEntity, createFakePlayer, createFakeTruck } from "./fake_world.mjs";

const main = await import("../../behavior_packs/MonsterTruck_BP/scripts/main.js");

const GROUND_Y = 61;
const overworld = createFakeDimension();
overworld.fillLayer(GROUND_Y - 1, "minecraft:stone");
fake.dimensions.overworld = overworld; // nether and the_end are missing: the loop skips them

function addTruck(options) {
  const truck = createFakeTruck(options);
  overworld.entities.push(truck);
  return truck;
}

function addPlayer(id) {
  const player = createFakePlayer({ id });
  fake.entities.set(id, player);
  return player;
}

test("driverInput reads the driver's movement vector and the held Jump button (handbrake)", () => {
  const press = (state) => ({
    inputInfo: {
      getMovementVector: () => ({ x: 0.5, y: 1 }),
      getButtonState: (button) => (button === InputButton.Jump ? state : ButtonState.Released),
    },
  });
  assert.deepEqual(main.driverInput.movement(press(ButtonState.Released)), { x: 0.5, y: 1 });
  assert.equal(main.driverInput.handbrake(press(ButtonState.Pressed)), true);
  assert.equal(main.driverInput.handbrake(press(ButtonState.Released)), false);
});

test("main runs one tick loop and a before-hurt handler; Jump launches nothing (ADR-0017)", () => {
  assert.equal(fake.intervals.length, 1);
  assert.equal(fake.hurtHandlers.length, 1);
  assert.deepEqual(fake.afterEventSubscriptions, [], "no playerButtonInput or other after-event");
  assert.equal(main.requestDriverJump, undefined, "the Suspension Jump entry point is retired");
});

test("the tick loop drives every valid truck through the driverInput seam", () => {
  const driver = addPlayer("loop-driver");
  const truck = addTruck({ location: { x: 40.5, y: GROUND_Y, z: 0.5 }, riders: [driver] });
  const parked = addTruck({ location: { x: -40.5, y: GROUND_Y, z: 0.5 } });
  parked.isValid = false;
  const { movement } = main.driverInput;
  main.driverInput.movement = () => ({ x: 1, y: 0 }); // as Scenario Runs override it
  try {
    runTick();
  } finally {
    main.driverInput.movement = movement;
  }
  assert.ok(truck.properties["blake:steer_angle"] < 0, "A from the seam turns the wheels left");
  assert.deepEqual(parked.properties, {}, "invalid trucks are skipped");
});

test("riders take no fall damage during a drop and its landing window, then protection ends", () => {
  const rider = addPlayer("drop-rider");
  const bystander = addPlayer("drop-bystander");
  const truck = addTruck({ location: { x: 0.5, y: GROUND_Y + 4, z: 40.5 }, isOnGround: false, riders: [rider] });
  runTick();
  assert.equal(hurt(rider, "fall").cancel, false, "no protection before a drop");

  truck.moveTo({ y: GROUND_Y + 3.5 }, { velocity: { y: -0.5 } });
  runTick();
  truck.moveTo({ y: GROUND_Y }, { velocity: { y: 0 }, isOnGround: true });
  runTick();
  assert.equal(hurt(rider, "fall").cancel, true, "landing fall damage is absorbed");
  assert.equal(hurt(rider, "entityAttack").cancel, false, "only fall damage is absorbed");
  assert.equal(hurt(bystander, "fall").cancel, false, "players outside the truck are not protected");

  for (let i = 0; i < 8; i++) runTick();
  assert.equal(hurt(rider, "fall").cancel, true, "still absorbed on the last tick of the landing window");
  runTick();
  assert.equal(hurt(rider, "fall").cancel, false, "protection follows the drop, not a standing time window");
});

test("the truck itself never takes fall damage", () => {
  const truck = addTruck({ location: { x: 80.5, y: GROUND_Y, z: 80.5 } });
  assert.equal(hurt(truck, "fall").cancel, true);
});

test("seated riders are shielded from heat damage", () => {
  const truck = addTruck({ location: { x: 120.5, y: GROUND_Y, z: 0.5 } });
  const rider = createFakePlayer({ id: "heat-rider" });
  rider.getComponent = (id) => (id === "minecraft:riding" ? { entityRidingOn: truck } : undefined);
  for (const cause of ["fire", "fireTick", "lava"]) assert.equal(hurt(rider, cause).cancel, true, cause);
  assert.equal(hurt(rider, "entityAttack").cancel, false);
  const walker = createFakePlayer({ id: "heat-walker" });
  walker.getComponent = () => undefined;
  assert.equal(hurt(walker, "lava").cancel, false, "players on foot still burn");
});

test("a player's fatal blow returns exactly one Vehicle Item; other damage does not", () => {
  const truck = addTruck({ location: { x: 160.5, y: GROUND_Y, z: 0.5 } });
  const spawned = [];
  truck.dimension = { spawnItem: (item, location) => spawned.push({ item, location }) };
  truck.getComponent = (id) => (id === "minecraft:health" ? { currentValue: 100 } : undefined);
  let removed = 0;
  truck.remove = () => {
    removed += 1;
  };
  const player = createFakePlayer({ id: "retriever" });
  const zombie = createFakeEntity({ typeId: "minecraft:zombie" });

  assert.equal(hurt(truck, "entityAttack", { damage: 50, damagingEntity: player }).cancel, false, "non-fatal hits damage the truck");
  assert.equal(hurt(truck, "entityAttack", { damage: 100, damagingEntity: zombie }).cancel, false, "mob kills drop Scrap");
  assert.equal(fake.runs.length, 0);

  const runsBefore = fake.runs.length;
  assert.equal(hurt(truck, "entityAttack", { damage: 100, damagingEntity: player }).cancel, true);
  assert.equal(fake.runs.length, runsBefore + 1);
  fake.runs.at(-1)();
  assert.equal(spawned.length, 1);
  assert.ok(spawned[0].item instanceof ItemStack);
  assert.equal(spawned[0].item.typeId, "blake:monster_truck_vehicle");
  assert.equal(spawned[0].item.amount, 1);
  assert.deepEqual(spawned[0].location, { x: 160.5, y: GROUND_Y, z: 0.5 });
  assert.equal(removed, 1);
});
