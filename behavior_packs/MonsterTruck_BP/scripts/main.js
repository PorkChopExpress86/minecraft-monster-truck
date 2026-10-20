import {
  system,
  world,
  ButtonState,
  InputButton,
  InputPermissionCategory,
  ItemStack
} from "@minecraft/server";
import { shouldShieldRiderFromHeat } from "./amphibious.js";
import { DURABILITY, DURABILITY_PROPERTY, gaugeHealth, hitCost } from "./durability.js";
import { absorbsFallDamage } from "./landing.js";
import { createTruckState, releaseTruck, tickTruck } from "./truck_tick.js";

// Track state of each truck across ticks; a truck's state is dropped once it is gone.
const truckStates = new Map();
const protectedRiders = new Map();
// Durability left and the immunity window of each truck hit this session, so hits in one tick see each other
// before the stored value is written (ADR-0020).
const truckDurability = new Map();
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

// Minecraft dismounts a rider who presses Space, the handbrake. With the Jump input permission off it does
// not, and inputInfo still reads Jump (#40, docs/agents/bedrock-physics.md), so seated players have Jump
// off. JUMP_LOCK marks a player whose Jump the add-on turned off: Jump comes back on only for them, also
// after they left the world mid-ride, and never for a player someone else turned it off for.
export const JUMP_LOCK = "blake:jump_locked";

function lockJump(player, seated) {
  try {
    const permissions = player.inputPermissions;
    if (seated) {
      if (permissions.isPermissionCategoryEnabled(InputPermissionCategory.Jump)) {
        permissions.setPermissionCategory(InputPermissionCategory.Jump, false);
        player.setDynamicProperty(JUMP_LOCK, true);
      }
    } else if (player.getDynamicProperty(JUMP_LOCK) === true) {
      permissions.setPermissionCategory(InputPermissionCategory.Jump, true);
      player.setDynamicProperty(JUMP_LOCK);
    }
  } catch {}
}

function onTick() {
  const presentTrucks = new Set();
  const seatedPlayers = new Set();
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
      try {
        for (const rider of truck.getComponent("minecraft:rideable")?.getRiders() ?? []) {
          if (rider?.typeId === "minecraft:player") seatedPlayers.add(rider.id);
        }
      } catch {}
    }
  }

  // A hidden truck may still carry a player, so Jump is only turned back on when every truck was seen.
  try {
    for (const player of world.getAllPlayers()) {
      const seated = seatedPlayers.has(player.id);
      if (seated || sawEveryTruck) lockJump(player, seated);
    }
  } catch {}

  if (!sawEveryTruck) return;
  for (const [truckId, state] of truckStates) {
    if (presentTrucks.has(truckId)) continue;
    releaseTruck(truckId, state, tickInput);
    truckStates.delete(truckId);
    truckDurability.delete(truckId);
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

function durabilityState(truck) {
  let state = truckDurability.get(truck.id);
  if (!state) {
    let stored;
    try {
      stored = truck.getDynamicProperty(DURABILITY_PROPERTY);
    } catch {}
    // A truck placed before Durability existed has none stored and starts full.
    state = { durability: typeof stored === "number" ? stored : DURABILITY };
    truckDurability.set(truck.id, state);
  }
  return state;
}

function recordDurability(truck, durability) {
  system.run(() => {
    if (!truck.isValid) return;
    try {
      truck.setDynamicProperty(DURABILITY_PROPERTY, durability);
    } catch {}
    try {
      truck.getComponent("minecraft:health")?.setCurrentValue(gaugeHealth(durability));
    } catch {}
  });
}

function retrieve(truck) {
  const location = { ...truck.location };
  const dimension = truck.dimension;
  system.run(() => {
    if (!truck.isValid) return;
    dimension.spawnItem(new ItemStack("blake:monster_truck_vehicle", 1), location);
    truck.remove();
  });
}

// Charges a hit on a truck to its Durability. A hit it survives is cancelled and the gauge follows. The blow
// that uses it up is a player's deliberate retrieval, which returns the Vehicle Item, or from anything else a
// killing blow the engine applies with its own cause, so the loot table drops Scrap.
function chargeTruckHit(event) {
  const truck = event.hurtEntity;
  const state = durabilityState(truck);
  if (state.retrieving) {
    event.cancel = true;
    return;
  }
  if (state.durability > 0) {
    const tick = typeof system.currentTick === "number" ? system.currentTick : currentTick;
    const cost = hitCost(state, event.damageSource?.cause, event.damage, tick);
    if (cost === 0) {
      event.cancel = true;
      return;
    }
    state.durability -= cost;
    if (state.durability > 0) {
      event.cancel = true;
      recordDurability(truck, state.durability);
      return;
    }
    if (event.damageSource?.damagingEntity?.typeId === "minecraft:player") {
      event.cancel = true;
      state.retrieving = true;
      retrieve(truck);
      return;
    }
  }
  // The gauge holds at most GAUGE_HEALTH, so a blow of the full Durability kills through it.
  event.damage = Math.max(event.damage, DURABILITY);
}

if (world.beforeEvents && world.beforeEvents.entityHurt) {
  try {
    world.beforeEvents.entityHurt.subscribe((event) => {
      if (isPneumaticallyProtectedFall(event) || isThermallyShieldedRider(event)) {
        event.cancel = true;
      } else if (event.hurtEntity?.typeId === "blake:monster_truck") {
        chargeTruckHit(event);
      }
    });
  } catch {}
}
