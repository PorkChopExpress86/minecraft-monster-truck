// Behaviour tests for main.js: the driverInput seam, what it subscribes to, its tick loop, and
// the before-hurt rules (Pneumatic Shock Absorption, thermal shielding, Durability, Vehicle Item retrieval).
// main.js is loaded against the fake @minecraft/server in fake_server.mjs.
import { test } from "node:test";
import assert from "node:assert/strict";

import { ButtonState, InputButton, InputPermissionCategory, ItemStack, fake, hurt, runTick } from "./fake_server.mjs";
import { createFakeDimension, createFakeEntity, createFakePlayer, createFakeTruck } from "./fake_world.mjs";

const main = await import("../../behavior_packs/MonsterTruck_BP/scripts/main.js");
const { DURABILITY_PROPERTY } = await import("../../behavior_packs/MonsterTruck_BP/scripts/durability.js");

const GROUND_Y = 61;
const overworld = createFakeDimension();
overworld.fillLayer(GROUND_Y - 1, "minecraft:stone");
fake.dimensions.overworld = overworld;
fake.dimensions.nether = createFakeDimension(); // empty, as the vanilla dimensions always resolve
fake.dimensions.the_end = createFakeDimension();

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

// Durability (ADR-0020): the truck's minecraft:health is a one-row gauge; the hurt handler charges each hit
// to the Durability stored on the truck and keeps the gauge in step.
const durability = (truck) => truck.getDynamicProperty(DURABILITY_PROPERTY);

function addRetrievalTruck(x, storedDurability) {
  const truck = addTruck({ location: { x, y: GROUND_Y, z: 0.5 } });
  if (storedDurability !== undefined) truck.setDynamicProperty(DURABILITY_PROPERTY, storedDurability);
  truck.spawned = [];
  truck.dimension = { spawnItem: (item, location) => truck.spawned.push({ item, location }) };
  truck.removed = 0;
  truck.remove = () => {
    truck.removed += 1;
    truck.isValid = false; // as the engine does for a removed entity
  };
  return truck;
}

function runScheduled(runsBefore) {
  for (const run of fake.runs.slice(runsBefore)) run();
}

test("a hit the truck survives comes off its Durability, not its health, and moves the gauge", () => {
  const truck = addRetrievalTruck(160.5);
  const zombie = createFakeEntity({ typeId: "minecraft:zombie" });
  const runsBefore = fake.runs.length;
  const event = hurt(truck, "entityAttack", { damage: 400, damagingEntity: zombie });
  assert.equal(event.cancel, true, "the engine applies no damage");
  runScheduled(runsBefore);
  assert.equal(durability(truck), 900, "a quarter of 400");
  assert.equal(truck.health, 18, "900 of 1000 shows as 9 hearts");
  assert.equal(truck.spawned.length, 0);
});

test("a truck with no stored Durability, such as one placed before it existed, starts full", () => {
  const truck = addRetrievalTruck(170.5);
  const runsBefore = fake.runs.length;
  hurt(truck, "lava", { damage: 4 });
  runScheduled(runsBefore);
  assert.equal(durability(truck), 996);
});

test("a player's blow that uses up the Durability returns exactly one Vehicle Item", () => {
  const truck = addRetrievalTruck(180.5, 5);
  const player = createFakePlayer({ id: "retriever" });
  const runsBefore = fake.runs.length;
  assert.equal(hurt(truck, "entityAttack", { damage: 40, damagingEntity: player }).cancel, true);
  runScheduled(runsBefore);
  assert.equal(truck.spawned.length, 1);
  assert.ok(truck.spawned[0].item instanceof ItemStack);
  assert.equal(truck.spawned[0].item.typeId, "blake:monster_truck_vehicle");
  assert.equal(truck.spawned[0].item.amount, 1);
  assert.deepEqual(truck.spawned[0].location, { x: 180.5, y: GROUND_Y, z: 0.5 });
  assert.equal(truck.removed, 1);
});

test("a player's blow the truck survives returns nothing", () => {
  const truck = addRetrievalTruck(190.5, 500);
  const runsBefore = fake.runs.length;
  hurt(truck, "entityAttack", { damage: 40, damagingEntity: createFakePlayer({ id: "puncher" }) });
  runScheduled(runsBefore);
  assert.equal(durability(truck), 490);
  assert.equal(truck.spawned.length, 0);
  assert.equal(truck.removed, 0);
});

test("a mob's or hazard's blow that uses up the Durability lets the engine destroy the truck for Scrap", () => {
  const zombie = createFakeEntity({ typeId: "minecraft:zombie" });
  for (const [cause, damagingEntity] of [["entityAttack", zombie], ["lava", undefined], ["lightning", undefined]]) {
    const truck = addRetrievalTruck(200.5, 5);
    const runsBefore = fake.runs.length;
    const event = hurt(truck, cause, { damage: 40, damagingEntity });
    runScheduled(runsBefore);
    assert.equal(event.cancel, false, `${cause}: the engine applies the killing blow, so the loot table drops Scrap`);
    assert.ok(event.damage >= truck.health, `${cause}: the blow is raised to kill the truck through its gauge`);
    assert.equal(truck.spawned.length, 0, `${cause}: no Vehicle Item`);
    assert.equal(truck.removed, 0, cause);
  }
});

test("two fatal blows in one tick return one Vehicle Item, not two", () => {
  const truck = addRetrievalTruck(220.5, 5);
  const runsBefore = fake.runs.length;
  for (const id of ["retriever-a", "retriever-b"]) {
    assert.equal(hurt(truck, "entityAttack", { damage: 100, damagingEntity: createFakePlayer({ id }) }).cancel, true);
  }
  runScheduled(runsBefore);
  assert.deepEqual(truck.spawned.map((drop) => drop.item.typeId), ["blake:monster_truck_vehicle"]);
  assert.equal(truck.isValid, false);
});

function removeTruck(truck) {
  overworld.entities.splice(overworld.entities.indexOf(truck), 1);
}

test("a truck gone from the world takes its tick state with it", () => {
  const truck = addTruck({ location: { x: 200.5, y: GROUND_Y, z: 0.5 } });
  runTick();
  removeTruck(truck);
  runTick();

  // The same truck comes back 30 blocks away (a reloaded chunk), parked, with a mob ahead.
  truck.moveTo({ z: 30.5 }, { velocity: { z: 0 } });
  const zombie = createFakeEntity({ location: { x: 200.5, y: GROUND_Y, z: 33 } });
  overworld.entities.push(truck, zombie);
  runTick();
  assert.equal(zombie.damage.length, 0, "a fresh state measures no motion, so a parked truck tramples nothing");
});

test("a rider protected by a truck that is gone mid-drop loses fall protection", () => {
  const rider = addPlayer("orphaned-rider");
  const truck = addTruck({ location: { x: 240.5, y: GROUND_Y + 6, z: 0.5 }, isOnGround: false, riders: [rider] });
  runTick();
  truck.moveTo({ y: GROUND_Y + 5.5 }, { velocity: { y: -0.5 } });
  runTick();
  assert.equal(hurt(rider, "fall").cancel, true, "protected while the truck falls");
  removeTruck(truck);
  runTick();
  assert.equal(hurt(rider, "fall").cancel, false, "protection ends with the truck");
});

test("a dimension that cannot be fetched hides its trucks, so their state and riders are kept", () => {
  const rider = addPlayer("hidden-rider");
  const truck = addTruck({ location: { x: 280.5, y: GROUND_Y + 6, z: 0.5 }, isOnGround: false, riders: [rider] });
  runTick();
  truck.moveTo({ y: GROUND_Y + 5.5 }, { velocity: { y: -0.5 } });
  runTick();
  assert.equal(hurt(rider, "fall").cancel, true, "protected while the truck falls");

  delete fake.dimensions.overworld; // world.getDimension("overworld") throws this tick
  try {
    runTick();
  } finally {
    fake.dimensions.overworld = overworld;
  }
  assert.equal(hurt(rider, "fall").cancel, true, "a failed lookup does not end the drop's protection");
});

// Minecraft dismounts a rider who presses Space, the handbrake; with the Jump input permission off it
// does not, and Jump still reads as pressed (#40, docs/agents/bedrock-physics.md).
const jumpEnabled = (player) => player.inputPermissions.isPermissionCategoryEnabled(InputPermissionCategory.Jump);

test("a seated player's Jump is off while in the truck and back on once out of it", () => {
  const rider = addPlayer("jump-rider");
  const truck = addTruck({ location: { x: 320.5, y: GROUND_Y, z: 0.5 }, riders: [rider] });
  runTick();
  assert.equal(jumpEnabled(rider), false, "Space cannot dismount a seated player");
  truck.detach(rider); // left by Sneak
  runTick();
  assert.equal(jumpEnabled(rider), true, "Jump works again on foot");
  assert.equal(rider.getDynamicProperty(main.JUMP_LOCK), undefined);
});

test("a rider whose truck is gone gets Jump back", () => {
  const rider = addPlayer("jump-orphan");
  const truck = addTruck({ location: { x: 360.5, y: GROUND_Y, z: 0.5 }, riders: [rider] });
  runTick();
  assert.equal(jumpEnabled(rider), false);
  removeTruck(truck);
  runTick();
  assert.equal(jumpEnabled(rider), true);
});

test("a player who left the world mid-ride gets Jump back when they return", () => {
  const returning = addPlayer("jump-returning");
  returning.inputPermissions.setPermissionCategory(InputPermissionCategory.Jump, false);
  returning.setDynamicProperty(main.JUMP_LOCK, true);
  runTick();
  assert.equal(jumpEnabled(returning), true);
  assert.equal(returning.getDynamicProperty(main.JUMP_LOCK), undefined);
});

test("a Jump permission turned off by someone else stays off, in the truck and out of it", () => {
  const player = addPlayer("jump-mapmaker");
  player.inputPermissions.setPermissionCategory(InputPermissionCategory.Jump, false);
  runTick();
  assert.equal(jumpEnabled(player), false, "not the add-on's to turn on");
  const truck = addTruck({ location: { x: 400.5, y: GROUND_Y, z: 0.5 }, riders: [player] });
  runTick();
  truck.detach(player);
  runTick();
  assert.equal(jumpEnabled(player), false, "still off after a ride");
});

test("a dimension that cannot be fetched turns no seated rider's Jump back on", () => {
  const rider = addPlayer("jump-hidden");
  addTruck({ location: { x: 440.5, y: GROUND_Y, z: 0.5 }, riders: [rider] });
  runTick();
  delete fake.dimensions.overworld;
  try {
    runTick();
  } finally {
    fake.dimensions.overworld = overworld;
  }
  assert.equal(jumpEnabled(rider), false, "the hidden truck may still carry the rider");
});
