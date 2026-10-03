import {
  system,
  world,
  ButtonState,
  InputButton,
  ItemStack
} from "@minecraft/server";
import { shouldShieldRiderFromHeat } from "./amphibious.js";
import { absorbsFallDamage } from "./landing.js";
import { createTruckState, releaseTruck, tickTruck } from "./truck_tick.js";

// Track state of each truck across ticks; a truck's state is dropped once it is gone.
const truckStates = new Map();
const protectedRiders = new Map();
let currentTick = 0;
const DIMENSIONS = ["overworld", "nether", "the_end"];

// Driver input: movement ({ x: strafe, y: forward }) and the held Jump button, which is the
// handbrake. Exported so Scenario Runs can supply the input a Simulated Driver's inputInfo
// never reports (ADR-0016).
export const driverInput = {
  movement: (driver) => driver.inputInfo.getMovementVector(),
  handbrake: (driver) => driver.inputInfo.getButtonState(InputButton.Jump) === ButtonState.Pressed,
};

/** @type {import("./truck_tick.js").TickInput} */
const tickInput = {
  driverInput,
  getEntity: (id) => world.getEntity(id),
  protectedRiders,
};

function onTick() {
  const presentTrucks = new Set();
  // A failed dimension lookup or truck query hides that dimension's trucks, so nothing is
  // known to be gone.
  let sawEveryTruck = true;
  for (const dimName of DIMENSIONS) {
    /** @type {import("@minecraft/server").Dimension} */
    let dimension;
    try {
      dimension = world.getDimension(dimName);
    } catch {
      sawEveryTruck = false;
      continue;
    }
    if (!dimension) {
      sawEveryTruck = false;
      continue;
    }

    /** @type {import("@minecraft/server").Entity[]} */
    let trucks;
    try {
      trucks = dimension.getEntities({ type: "blake:monster_truck" });
    } catch {
      sawEveryTruck = false;
      continue;
    }

    for (const truck of trucks) {
      if (!truck || !truck.isValid) continue;
      presentTrucks.add(truck.id);

      const state = truckStates.get(truck.id) || createTruckState();
      truckStates.set(truck.id, state);
      const tickNumber = typeof system.currentTick === "number" ? system.currentTick : currentTick++;
      tickTruck(truck, dimension, state, tickInput, tickNumber);
    }
  }

  if (!sawEveryTruck) return;
  for (const [truckId, state] of truckStates) {
    if (presentTrucks.has(truckId)) continue;
    releaseTruck(truckId, state, tickInput);
    truckStates.delete(truckId);
  }
}

// Subscribe tick loop
system.runInterval(onTick, 1);

// Pneumatic Shock Absorption event handling for vehicle and riders
function isPneumaticallyProtectedFall(event) {
  const cause = event.damageSource ? event.damageSource.cause : undefined;
  return absorbsFallDamage(cause, event.hurtEntity, protectedRiders);
}

function isThermallyShieldedRider(event) {
  try {
    const vehicle = event.hurtEntity?.getComponent("minecraft:riding")?.entityRidingOn;
    return shouldShieldRiderFromHeat(event.damageSource?.cause, vehicle?.typeId === "blake:monster_truck");
  } catch {
    return false;
  }
}

function isDeliberateRetrieval(event) {
  const truck = event.hurtEntity;
  const player = event.damageSource?.damagingEntity;
  if (truck?.typeId !== "blake:monster_truck" || player?.typeId !== "minecraft:player") {
    return false;
  }

  try {
    const health = truck.getComponent("minecraft:health");
    return event.damage >= health.currentValue;
  } catch {
    return false;
  }
}

if (world.beforeEvents && world.beforeEvents.entityHurt) {
  try {
    world.beforeEvents.entityHurt.subscribe((event) => {
      if (isPneumaticallyProtectedFall(event) || isThermallyShieldedRider(event)) {
        event.cancel = true;
      } else if (isDeliberateRetrieval(event)) {
        event.cancel = true;
        const truck = event.hurtEntity;
        const location = { ...truck.location };
        const dimension = truck.dimension;
        system.run(() => {
          if (!truck.isValid) return;
          dimension.spawnItem(new ItemStack("blake:monster_truck_vehicle", 1), location);
          truck.remove();
        });
      }
    });
  } catch {}
}
