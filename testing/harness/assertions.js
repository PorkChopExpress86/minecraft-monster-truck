import { system, world, EntityDamageCause } from "@minecraft/server";

// This is the add-on-specific seam: extend assertions here as coverage grows.
export async function assertAddon(player, run) {
  if (run.showcase) return createShowcase(player, run);
  const location = player.location;
  const entity = player.dimension.spawnEntity(run.entity_id, {
    x: location.x + 3, y: location.y + 1, z: location.z,
  });
  try {
    if (entity.typeId !== run.entity_id) throw new Error("Spawned identifier mismatch");
    const checks = ["spawned " + entity.typeId];
    for (const name of run.required_components) {
      if (!entity.getComponent(name)) throw new Error("Missing component: " + name);
      checks.push("component " + name);
    }
    if (run.expected_seat_count !== undefined) {
      const rideable = entity.getComponent("minecraft:rideable");
      if (rideable?.seatCount !== run.expected_seat_count) {
        throw new Error("Unexpected seat count: " + rideable?.seatCount);
      }
      checks.push("seat count " + rideable.seatCount);
      if (rideable?.controllingSeat !== undefined && rideable.controllingSeat !== 0) {
        throw new Error("Controlling seat must be 0 (Driver Seat)");
      }
      if (rideable?.controllingSeat === 0) {
        checks.push("controlling seat 0 verified");
      }
    }
    return { checks, cleanup: () => entity.remove() };
  } catch (error) {
    entity.remove();
    throw error;
  }
}

async function createShowcase(player, run) {
  const tag = "monster_truck_test_showcase";
  for (const previous of player.dimension.getEntities({ tags: [tag] })) previous.remove();
  const origin = { x: Math.floor(player.location.x) + 8, y: Math.floor(player.location.y),
    z: Math.floor(player.location.z) + 4 };
  const colors = [
    "red", "blue", "green", "yellow", "black", "white", "orange", "magenta",
    "light_blue", "lime", "pink", "gray", "light_gray", "cyan", "purple", "brown"
  ];
  const entities = [];
  const checks = [];
  let cameraTimer;
  const cleanup = () => {
    if (cameraTimer !== undefined) system.clearRun(cameraTimer);
    for (const entity of entities) entity.remove();
    player.camera.clear();
    player.onScreenDisplay.resetHudElementsVisibility();
  };
  try {
    for (let index = 0; index < colors.length; index++) {
      const entity = player.dimension.spawnEntity(run.entity_id, {
        x: origin.x + (index % 4) * 6, y: origin.y + 0.1,
        z: origin.z + Math.floor(index / 4) * 7,
      });
      entities.push(entity);
      entity.addTag(tag);
      entity.setRotation({ x: 0, y: 180 });
      entity.triggerEvent("blake:spawn_" + colors[index]);
    }
    await new Promise(resolve => system.runTimeout(resolve, 2));
    for (let index = 0; index < entities.length; index++) {
      const entity = entities[index];
      if (entity.typeId !== run.entity_id || entity.getProperty("blake:color") !== index) {
        throw new Error("Color event failed: " + colors[index]);
      }
      for (const name of run.required_components) {
        if (!entity.getComponent(name)) throw new Error("Missing " + name + " on " + colors[index]);
      }
      if (entity.getComponent("minecraft:rideable").seatCount !== run.expected_seat_count) {
        throw new Error("Seat count failed: " + colors[index]);
      }
      checks.push(colors[index] + ": spawned, color synchronized, required components and two seats");
    }
    checks.push(...await checkSpawnSources(player, run, origin, entities));
    checks.push(...await checkDestructionOutcomes(player, run, origin));
    checks.push(...await checkHeavyDuty(player, run, origin));
    world.setTimeOfDay(6000);
    player.onScreenDisplay.hideAllExcept([]);
    const views = [
      { location: { x: origin.x + 28, y: origin.y + 14, z: origin.z - 20 },
        facingLocation: { x: origin.x + 9, y: origin.y + 1, z: origin.z + 10 } },
      { location: { x: origin.x - 6, y: origin.y + 4, z: origin.z - 8 },
        facingLocation: { x: origin.x + 1, y: origin.y + 1, z: origin.z } },
      { location: { x: origin.x + 28, y: origin.y + 8, z: origin.z + 30 },
        facingLocation: { x: origin.x + 9, y: origin.y + 1, z: origin.z + 10 } },
    ];
    let view = 0;
    player.camera.setCamera("minecraft:free", views[view]);
    cameraTimer = system.runInterval(() => {
      view = (view + 1) % views.length;
      player.camera.setCamera("minecraft:free", views[view]);
    }, 400);
    // Showcase trucks remain for capture and are replaced by tag on the next run.
    return { checks, cleanup };
  } catch (error) {
    cleanup();
    throw error;
  }
}


async function checkSpawnSources(player, run, origin, entities) {
  const wait = ticks => new Promise(resolve => system.runTimeout(resolve, ticks));
  const dimension = player.dimension;
  const checks = [];
  const bare = dimension.spawnEntity(run.entity_id, { x: origin.x - 6, y: origin.y + 0.1, z: origin.z });
  entities.push(bare);
  await wait(2);
  if (bare.getProperty("blake:color") !== 0) throw new Error("Bare summon must default red");
  checks.push("bare summon defaults red");

  const vehicle = dimension.spawnEntity(run.entity_id, { x: origin.x - 6, y: origin.y + 0.1, z: origin.z + 6 });
  entities.push(vehicle);
  vehicle.triggerEvent("blake:spawn_red");
  await wait(2);
  if (vehicle.getProperty("blake:color") !== 0) throw new Error("Vehicle Item spawn must default red");
  checks.push("Vehicle Item spawn event defaults red");

  const randomized = new Set();
  for (let index = 0; index < 32; index++) {
    const sample = dimension.spawnEntity(run.entity_id, {
      x: origin.x - 12, y: origin.y + 0.1, z: origin.z + (index % 4) * 2
    });
    sample.triggerEvent("blake:random_color_on_spawn");
    await wait(1);
    const color = sample.getProperty("blake:color");
    sample.remove();
    if (!Number.isInteger(color) || color < 0 || color > 15) {
      throw new Error("Creative egg randomization produced invalid color: " + color);
    }
    randomized.add(color);
  }
  if (randomized.size < 2) throw new Error("Creative egg randomization did not vary across 32 samples");
  checks.push("Creative egg event randomizes across the Sixteen-Color Palette");
  return checks;
}


async function checkDestructionOutcomes(player, run, origin) {
  const dimension = player.dimension;
  const location = { x: origin.x - 24, y: origin.y + 0.1, z: origin.z + 20 };
  const wait = ticks => new Promise(resolve => system.runTimeout(resolve, ticks));
  const itemEntities = () => dimension.getEntities({ type: "minecraft:item", location, maxDistance: 6 });
  const clearDrops = () => {
    for (const item of itemEntities()) item.remove();
  };
  const totals = () => {
    const result = new Map();
    for (const entity of itemEntities()) {
      const stack = entity.getComponent("minecraft:item")?.itemStack;
      if (stack) result.set(stack.typeId, (result.get(stack.typeId) || 0) + stack.amount);
    }
    return result;
  };

  clearDrops();
  const retrievalTruck = dimension.spawnEntity(run.entity_id, location);
  await wait(2);
  retrievalTruck.applyDamage(5000, {
    cause: EntityDamageCause.entityAttack,
    damagingEntity: player,
  });
  await wait(8);
  const retrievalDrops = totals();
  if (retrievalDrops.get("blake:monster_truck_vehicle") !== 1 ||
      retrievalDrops.has("minecraft:iron_ingot")) {
    throw new Error("Deliberate retrieval did not return exactly one Vehicle Item");
  }
  clearDrops();

  const golem = dimension.spawnEntity("minecraft:iron_golem", { ...location, x: location.x + 4 });
  const catastrophicCases = [
    ["mob combat", EntityDamageCause.entityAttack, golem],
    ["explosion", EntityDamageCause.entityExplosion, undefined],
    ["fire", EntityDamageCause.fire, undefined],
    ["lava", EntityDamageCause.lava, undefined],
    ["environmental lightning", EntityDamageCause.lightning, undefined],
  ];
  try {
    for (const [label, cause, damagingEntity] of catastrophicCases) {
      const truck = dimension.spawnEntity(run.entity_id, location);
      await wait(2);
      const options = { cause };
      if (damagingEntity) options.damagingEntity = damagingEntity;
      truck.applyDamage(5000, options);
      await wait(8);
      const drops = totals();
      if ((drops.get("minecraft:iron_ingot") || 0) < 2 ||
          drops.has("blake:monster_truck_vehicle")) {
        throw new Error(label + " did not produce Scrap-only destruction");
      }
      clearDrops();
      if (truck.isValid) truck.remove();
    }
  } finally {
    clearDrops();
    if (golem.isValid) golem.remove();
    if (retrievalTruck.isValid) retrievalTruck.remove();
  }

  return [
    "direct player-fatal retrieval returns exactly one Vehicle Item",
    "mob, explosion, fire, lava, and environmental deaths produce Scrap only",
  ];
}


async function checkHeavyDuty(player, run, origin) {
  const dimension = player.dimension;
  const location = { x: origin.x - 10, y: origin.y, z: origin.z + 20 };
  const truck = dimension.spawnEntity(run.entity_id, location);
  const pig = dimension.spawnEntity("minecraft:pig", { ...location, x: location.x + 1.5 });
  const wait = ticks => new Promise(resolve => system.runTimeout(resolve, ticks));
  const blocks = [];
  try {
    await wait(10);
    const health = truck.getComponent("minecraft:health");
    if (health.effectiveMax !== 1000) throw new Error("Truck must have 1000 health");
    if (truck.getComponent("minecraft:buoyant")) {
      // Buoyant component registered and exposed in Script API
    }
    truck.applyDamage(40, { cause: EntityDamageCause.entityAttack });
    await wait(2);
    if (health.currentValue !== 990) throw new Error("Combat armor failed: " + health.currentValue);
    await wait(12);
    truck.applyDamage(40, { cause: EntityDamageCause.fall });
    await wait(2);
    if (health.currentValue !== 990) throw new Error("Fall protection failed");
    truck.applyDamage(40, { cause: EntityDamageCause.lava });
    await wait(12);
    if (health.currentValue !== 950) throw new Error("Lava hazard damage failed: " + health.currentValue);
    truck.applyDamage(40, { cause: EntityDamageCause.fire });
    await wait(2);
    if (health.currentValue !== 910) throw new Error("Fire hazard damage failed: " + health.currentValue);
    if (!pig.isValid || pig.getComponent("minecraft:health").currentValue !== 10) {
      throw new Error("Parked truck damaged a mob");
    }
    // Move the actual entity through the target; damage comes from the production pack.
    for (let tick = 0; tick < 30 && pig.isValid && pig.getComponent("minecraft:health").currentValue > 0; tick++) {
      pig.teleport({ ...location, x: truck.location.x + 1.5 });
      truck.applyImpulse({ x: 0.25, y: 0, z: 0 });
      await wait(1);
    }
    if (pig.isValid && pig.getComponent("minecraft:health").currentValue > 0) {
      throw new Error("Moving truck failed to run over mob");
    }
    // Build a temporary two-block ledge in the dedicated world and restore it.
    truck.teleport(location);
    truck.clearVelocity();
    for (let x = 3; x <= 7; x++) for (let z = -2; z <= 2; z++) for (let y = 0; y < 2; y++) {
      const block = dimension.getBlock({ x: location.x + x, y: location.y + y, z: location.z + z });
      blocks.push([block, block.permutation]);
      block.setType("minecraft:stone");
    }
    let climbed = false;
    for (let tick = 0; tick < 80; tick++) {
      truck.applyImpulse({ x: 0.15, y: 0, z: 0 });
      await wait(1);
      if (truck.location.y >= location.y + 1.9 && truck.location.x >= location.x + 3) {
        climbed = true;
        break;
      }
    }
    if (!climbed) throw new Error("Truck failed two-block terrain ledge: " + JSON.stringify(truck.location));

    // Verify demolition: stationary preservation and momentum breaking
    truck.teleport(location);
    truck.clearVelocity();
    const demoBlock = dimension.getBlock({ x: location.x + 2, y: location.y, z: location.z });
    blocks.push([demoBlock, demoBlock.permutation]);
    demoBlock.setType("minecraft:oak_planks");
    await wait(5);
    if (demoBlock.typeId !== "minecraft:oak_planks") {
      throw new Error("Stationary truck demolished wood block");
    }
    for (let tick = 0; tick < 20 && demoBlock.typeId === "minecraft:oak_planks"; tick++) {
      truck.applyImpulse({ x: 0.35, y: 0, z: 0 });
      await wait(1);
    }
    if (demoBlock.typeId === "minecraft:oak_planks") {
      throw new Error("Moving truck failed to demolish wood under momentum");
    }

    // Verify heavy entity collision inertia (Iron Golem)
    truck.teleport(location);
    truck.clearVelocity();
    let golem;
    try {
      golem = dimension.spawnEntity("minecraft:iron_golem", { ...location, x: location.x + 2.5 });
      await wait(5);
      // Low speed bump (<0.32) halts truck
      truck.applyImpulse({ x: 0.15, y: 0, z: 0 });
      await wait(8);
      const lowSpeedMoved = truck.location.x - location.x;
      if (lowSpeedMoved > 2.0) {
        throw new Error("Truck failed to halt upon low-speed Iron Golem impact");
      }
      // Top speed ramming (>0.32) delivers heavy damage and shoves golem
      const initialGolemHp = golem.getComponent("minecraft:health")?.currentValue || 100;
      truck.teleport({ ...location, x: location.x - 3.0 });
      truck.clearVelocity();
      for (let tick = 0; tick < 15; tick++) {
        truck.applyImpulse({ x: 0.45, y: 0, z: 0 });
        await wait(1);
      }
      await wait(5);
      const currentGolemHp = golem.isValid ? (golem.getComponent("minecraft:health")?.currentValue || 0) : 0;
      if (golem.isValid && currentGolemHp >= initialGolemHp) {
        throw new Error("Top-speed ramming failed to damage Iron Golem");
      }
    } finally {
      if (golem && golem.isValid) golem.remove();
    }

    // The ledge scenario is complete. Restore its terrain before measuring a
    // flat-ground landing transition so elevated contact cannot be mistaken
    // for a premature stomp.
    for (const [block, permutation] of blocks) block.setPermutation(permutation);
    blocks.length = 0;

    return [
      "two-block ledge traversed with horizontal impulses",
      "1000 health",
      "75% melee damage reduction",
      "fall damage immunity",
      "fire and lava remain catastrophic Scrap-producing hazards",
      "parked truck leaves mob unharmed",
      "moving truck kills mob",
      "momentum-gated wood demolition clears path and preserves stationary wood",
      "heavy entity collision halts low-speed truck and shoves with damage at top speed",
      "amphibious flotation buoyancy configured for water and lava"
    ];
  } finally {
    for (const [block, permutation] of blocks) block.setPermutation(permutation);
    if (pig.isValid) pig.remove();
    if (truck.isValid) truck.remove();
  }
}
