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
  const colors = ["red", "blue", "green", "yellow", "black", "white"];
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
        x: origin.x + (index % 3) * 6, y: origin.y + 0.1,
        z: origin.z + Math.floor(index / 3) * 8,
      });
      entities.push(entity);
      entity.addTag(tag);
      entity.setRotation({ x: 0, y: 180 });
      entity.triggerEvent("blake:paint_" + colors[index]);
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
    checks.push(...await checkHeavyDuty(player, run, origin));
    world.setTimeOfDay(6000);
    player.onScreenDisplay.hideAllExcept([]);
    const views = [
      { location: { x: origin.x + 19, y: origin.y + 10, z: origin.z - 18 },
        facingLocation: { x: origin.x + 6, y: origin.y + 1, z: origin.z + 4 } },
      { location: { x: origin.x - 6, y: origin.y + 4, z: origin.z - 8 },
        facingLocation: { x: origin.x + 1, y: origin.y + 1, z: origin.z } },
      { location: { x: origin.x + 19, y: origin.y + 6, z: origin.z + 13 },
        facingLocation: { x: origin.x + 6, y: origin.y + 1, z: origin.z + 4 } },
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
    truck.applyDamage(40, { cause: EntityDamageCause.entityAttack });
    await wait(2);
    if (health.currentValue !== 990) throw new Error("Combat armor failed: " + health.currentValue);
    await wait(12);
    truck.applyDamage(40, { cause: EntityDamageCause.fall });
    await wait(2);
    if (health.currentValue !== 990) throw new Error("Fall protection failed");
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
    return ["two-block ledge traversed with horizontal impulses", "1000 health", "75% melee damage reduction", "fall damage immunity", "parked truck leaves mob unharmed", "moving truck kills mob"];
  } finally {
    for (const [block, permutation] of blocks) block.setPermutation(permutation);
    if (pig.isValid) pig.remove();
    if (truck.isValid) truck.remove();
  }
}
