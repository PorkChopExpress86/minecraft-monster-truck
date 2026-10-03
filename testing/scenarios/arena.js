import { system } from "@minecraft/server";
import { driverInput } from "../main.js";

// Shared Scenario World helpers. The arena is a strip of the flat starter world
// (bedrock -64, dirt -63..-62, grass -61) extending +Z (yaw 0) from the origin.

export const wait = ticks => new Promise(resolve => system.runTimeout(resolve, ticks));

export function fill(dimension, from, to, block) {
  const a = [from.x, from.y, from.z].map(Math.floor).join(" ");
  const b = [to.x, to.y, to.z].map(Math.floor).join(" ");
  dimension.runCommand(`fill ${a} ${b} ${block}`);
}

// Restore the arena to flat ground and remove everything but players.
export function resetArena(dimension, origin) {
  const x = Math.floor(origin.x);
  const z = Math.floor(origin.z);
  fill(dimension, { x: x - 12, y: -60, z: z - 6 }, { x: x + 12, y: -40, z: z + 40 }, "air");
  fill(dimension, { x: x - 12, y: -60, z: z + 41 }, { x: x + 12, y: -40, z: z + 80 }, "air");
  fill(dimension, { x: x - 12, y: -63, z: z - 6 }, { x: x + 12, y: -62, z: z + 80 }, "dirt");
  fill(dimension, { x: x - 12, y: -61, z: z - 6 }, { x: x + 12, y: -61, z: z + 80 }, "grass_block");
  for (const entity of dimension.getEntities({ location: origin, maxDistance: 120 })) {
    if (entity.typeId !== "minecraft:player") entity.remove();
  }
}

// Park a player clear of every arena build so fills never entomb it.
export function park(player, origin) {
  player.teleport({ x: origin.x - 10, y: -60, z: origin.z - 4 });
}

export function spawnTruck(dimension, run, location, yaw = 0) {
  const truck = dimension.spawnEntity(run.entity_id, location);
  truck.setRotation({ x: 0, y: yaw });
  return truck;
}

export function riders(truck) {
  return truck.getComponent("minecraft:rideable").getRiders();
}

// Seat a simulated player through real interaction and verify the seat it took.
export async function board(player, truck, seat) {
  const at = truck.location;
  player.teleport({ x: at.x - 2, y: at.y, z: at.z });
  await wait(4);
  player.interactWithEntity(truck);
  await wait(6);
  const seated = riders(truck);
  if (seated[seat]?.id !== player.id) {
    throw new Error(`${player.name} did not take seat ${seat}: riders=${seated.map(r => r?.name).join(",")}`);
  }
}

// Hold driver input for the given ticks; onTick(tick) may return true to stop early.
// forward/strafe follow the movement vector (strafe +1 is A, left); handbrake is the held Jump
// button. A Simulated Driver's inputInfo never reports either, so they are supplied through the
// add-on's driverInput seam for this driver only (ADR-0016).
export async function drive(driver, ticks, { forward = 1, strafe = 0, handbrake = false, onTick } = {}) {
  const { movement, handbrake: brake } = driverInput;
  driverInput.movement = player => (player.id === driver.id ? { x: strafe, y: forward } : movement(player));
  driverInput.handbrake = player => (player.id === driver.id ? handbrake : brake(player));
  try {
    for (let tick = 0; tick < ticks; tick++) {
      await wait(1);
      if (onTick && onTick(tick)) break;
    }
  } finally {
    driverInput.movement = movement;
    driverInput.handbrake = brake;
  }
}

export function health(entity) {
  return entity.getComponent("minecraft:health").currentValue;
}

export function horizontal(a, b) {
  return Math.hypot(a.x - b.x, a.z - b.z);
}
