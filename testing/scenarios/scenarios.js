import { ItemStack, world, EntityDamageCause } from "@minecraft/server";
import { requestDriverJump } from "../main.js";
import {
  board, drive, fill, health, horizontal, park, resetArena, riders, spawnTruck, wait,
} from "./arena.js";

// Mechanic scenarios for Scenario Runs. Each takes { dimension, origin, driver, run, spawnPlayer }
// and resolves to a list of passed checks or throws with the failed expectation.
// Spec-defining outcomes are hard-coded here; anything unexpected is reported, never loosened.

const GROUND_Y = -60;            // walking surface of the flat starter (grass top at -61)
const PLAYER_MAX_HEALTH = 20;
const TRUCK_MAX_HEALTH = 1000;
const PITCH_TOLERANCE = 5;       // degrees, agreed in #33
const PITCH_CLAMP = 35;          // degrees, ADR-0014
const PITCH_MAX_STEP = 15;       // degrees per tick: 0.2 smoothing of a full 70 degree swing, rounded up

const at = (origin, dx, dz, y = GROUND_Y) => ({ x: origin.x + dx, y, z: origin.z + dz });

// Record every hurt event caused by a truck while fn runs.
async function recordTruckHits(fn) {
  const hits = [];
  const listener = world.afterEvents.entityHurt.subscribe(event => {
    if (event.damageSource.damagingEntity?.typeId === "blake:monster_truck") {
      hits.push({ target: event.hurtEntity, typeId: event.hurtEntity.typeId, damage: event.damage });
    }
  });
  try {
    await fn(hits);
  } finally {
    world.afterEvents.entityHurt.unsubscribe(listener);
  }
  return hits;
}

async function smoke({ dimension, origin, driver, run }) {
  if (!driver.isValid) throw new Error("Simulated Driver did not join");
  const truck = spawnTruck(dimension, run, at(origin, 4, 0));
  await wait(10);
  if (!truck.isValid || truck.typeId !== run.entity_id) throw new Error("Truck did not spawn");
  if (truck.getComponent("minecraft:rideable")?.seatCount !== 2) throw new Error("Truck must have two seats");
  return ["simulated driver joined", "spawned " + truck.typeId + " with two seats"];
}

async function seats({ dimension, origin, driver, run, spawnPlayer }) {
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  const passenger = spawnPlayer("SimulatedPassenger");
  await wait(10);
  await board(passenger, truck, 1);
  const parked = truck.location;
  passenger.setBodyRotation(0);
  passenger.moveRelative(0, 1, 1);
  await wait(30);
  passenger.stopMoving();
  const passengerMoved = horizontal(truck.location, parked);
  if (passengerMoved > 0.5) throw new Error(`Passenger Seat steered the truck ${passengerMoved.toFixed(2)} blocks`);
  const before = truck.location;
  await drive(driver, 20);
  const driverMoved = horizontal(truck.location, before);
  if (driverMoved < 5) throw new Error(`Driver Seat input moved the truck only ${driverMoved.toFixed(2)} blocks`);
  return ["driver took seat 0 and passenger seat 1 by interaction",
    `passenger input moved the truck ${passengerMoved.toFixed(2)} blocks (no steering authority)`,
    `driver input moved the truck ${driverMoved.toFixed(1)} blocks in 20 ticks`];
}

async function auto_step({ dimension, origin, driver, run }) {
  const checks = [];
  // Two-block ledge: climbed while driven, without jump input.
  fill(dimension, at(origin, -3, 10), at(origin, 3, 30, GROUND_Y + 1), "stone");
  let truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  let topY = truck.location.y;
  await drive(driver, 40, { onTick: () => { topY = Math.max(topY, truck.location.y); return truck.location.z > origin.z + 16; } });
  if (truck.location.z < origin.z + 12 || topY < GROUND_Y + 2 - 0.1) {
    throw new Error(`Controlled Auto-Step failed on a 2-block ledge: z=${(truck.location.z - origin.z).toFixed(1)} y=${topY.toFixed(2)}`);
  }
  if (topY - GROUND_Y > 2.5) {
    throw new Error(`Controlled Auto-Step launched the truck to +${(topY - GROUND_Y).toFixed(2)} on a 2-block ledge (Suspension Jump without jump input)`);
  }
  checks.push(`climbed a 2-block ledge while driven (reached +${(topY - GROUND_Y).toFixed(2)})`);
  truck.remove();
  park(driver, origin);
  await wait(5);
  // Three-block wall: needs a Suspension Jump, so driving alone must not clear it.
  resetArena(dimension, origin);
  fill(dimension, at(origin, -3, 10), at(origin, 3, 10, GROUND_Y + 2), "stone");
  truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 30);
  if (truck.location.z > origin.z + 10) throw new Error("Truck drove over a 3-block wall without a Suspension Jump");
  checks.push("a 3-block wall stops the truck without a jump");
  return checks;
}

async function suspension_jump({ dimension, origin, driver, run }) {
  fill(dimension, at(origin, -4, 12), at(origin, 4, 12, GROUND_Y + 2), "stone");
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  let peak = truck.location.y;
  let jumped = false;
  await drive(driver, 50, {
    onTick: () => {
      peak = Math.max(peak, truck.location.y);
      if (!jumped && truck.location.z >= origin.z + 7) {
        requestDriverJump(driver);
        jumped = true;
      }
      return truck.location.z > origin.z + 20;
    },
  });
  if (!jumped) throw new Error("Truck never reached the jump point");
  if (peak - GROUND_Y < 3) throw new Error(`Suspension Jump peaked only +${(peak - GROUND_Y).toFixed(2)} blocks`);
  if (truck.location.z <= origin.z + 13) throw new Error("Suspension Jump did not clear the 3-block wall");
  if (riders(truck)[0]?.id !== driver.id) throw new Error("Driver was ejected by the Suspension Jump");
  return [`Suspension Jump peaked +${(peak - GROUND_Y).toFixed(2)} blocks`, "cleared a 3-block wall with the driver still seated"];
}

async function crush_stomp({ dimension, origin, driver, run }) {
  const truck = spawnTruck(dimension, run, at(origin, 0, 4));
  await wait(10);
  await board(driver, truck, 0);
  const hits = await recordTruckHits(async () => {
    requestDriverJump(driver);
    await wait(8);
    // Place a mob under the descending truck's footprint.
    dimension.spawnEntity("minecraft:zombie", { ...truck.location, x: truck.location.x + 1, y: GROUND_Y });
    await wait(60);
  });
  const crush = hits.find(hit => hit.typeId === "minecraft:zombie");
  if (!crush) throw new Error("Crush Stomp landing did not damage the mob beneath");
  if (crush.damage < 60) throw new Error("Crush Stomp damage below lethal threshold: " + crush.damage);
  if (health(driver) !== PLAYER_MAX_HEALTH) throw new Error("Driver was hurt by the landing: " + health(driver));
  return [`Crush Stomp dealt ${crush.damage} damage to a mob beneath the landing`, "driver unhurt by the landing"];
}

async function shock_absorption({ dimension, origin, driver, run }) {
  // A 16-block mesa; drive off the edge with a Survival driver aboard.
  fill(dimension, at(origin, -4, 0), at(origin, 4, 8, GROUND_Y + 15), "stone");
  const top = GROUND_Y + 16;
  const truck = spawnTruck(dimension, run, at(origin, 0, 3, top));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 30, { onTick: () => truck.location.y < GROUND_Y + 0.5 });
  await wait(40);
  if (truck.location.y > GROUND_Y + 1) throw new Error("Truck never reached the ground: y=" + truck.location.y);
  if (health(driver) !== PLAYER_MAX_HEALTH) throw new Error("Rider took fall damage: health " + health(driver));
  if (health(truck) !== TRUCK_MAX_HEALTH) throw new Error("Truck took fall damage: health " + health(truck));
  if (riders(truck)[0]?.id !== driver.id) throw new Error("Driver was not kept seated through the drop");
  return ["16-block drop: rider and truck took no fall damage", "driver stayed seated through the landing"];
}

async function liquid_crossing({ dimension, origin, driver, run }, liquid) {
  // Liquid pool flush with the ground, then a 1-block-high bank.
  fill(dimension, at(origin, -5, 6, GROUND_Y - 3), at(origin, 5, 30, GROUND_Y - 1), liquid);
  fill(dimension, at(origin, -5, 31, GROUND_Y), at(origin, 5, 45, GROUND_Y), "stone");
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  let lowest = Infinity;
  let poolTicks = 0;
  await drive(driver, 120, {
    onTick: () => {
      const z = truck.location.z - origin.z;
      if (z > 9 && z < 28) {
        lowest = Math.min(lowest, truck.location.y);
        poolTicks++;
      }
      return z > 38;
    },
  });
  const checks = [];
  if (lowest < GROUND_Y - 1.5) throw new Error(`Truck sank in ${liquid}: lowest y ${(lowest - GROUND_Y).toFixed(2)}`);
  checks.push(`floated across ${liquid} (lowest ${(lowest - GROUND_Y).toFixed(2)} relative to the surface)`);
  checks.push(`crossed the pool mid-section in ${poolTicks} ticks (${(19 / Math.max(poolTicks, 1)).toFixed(2)} blocks/tick)`);
  if (truck.location.z - origin.z < 33 || truck.location.y < GROUND_Y + 0.9) {
    throw new Error(`Shoreline Step-Up failed: z=${(truck.location.z - origin.z).toFixed(1)} y=${(truck.location.y - GROUND_Y).toFixed(2)}`);
  }
  checks.push("Shoreline Step-Up onto a 1-block bank without a jump");
  if (riders(truck)[0]?.id !== driver.id) throw new Error("Driver lost the seat while crossing " + liquid);
  return { truck, checks };
}

async function flotation_water(context) {
  return (await liquid_crossing(context, "water")).checks;
}

async function flotation_lava(context) {
  const { dimension, origin, driver } = context;
  const { checks } = await liquid_crossing(context, "lava");
  if (health(driver) !== PLAYER_MAX_HEALTH || driver.getComponent("minecraft:onfire")) {
    throw new Error(`Rider not shielded from lava: health ${health(driver)}`);
  }
  checks.push("rider shielded from lava heat");
  // Molten Tire Trample: a heavy mob survives the hit, so ignition is observable.
  const golem = dimension.spawnEntity("minecraft:iron_golem", at(origin, 0, 43, GROUND_Y + 1));
  await wait(5);
  await drive(driver, 20, { onTick: () => golem.getComponent("minecraft:onfire") !== undefined });
  if (!golem.isValid || !golem.getComponent("minecraft:onfire")) throw new Error("Molten Tire Trample did not ignite the mob");
  checks.push("Molten Tire Trample ignited a mob after leaving lava");
  return checks;
}

async function trample({ dimension, origin, driver, run }) {
  const checks = [];
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  // Parked: a mob touching the tires is unharmed.
  const parkedHits = await recordTruckHits(async () => {
    dimension.spawnEntity("minecraft:pig", at(origin, 1.5, 2));
    await wait(30);
  });
  if (parkedHits.length) throw new Error("Parked truck damaged a mob");
  checks.push("parked truck does not trample");
  const firstHit = async (speed, dz) => {
    const target = dimension.spawnEntity("minecraft:pig", at(origin, 0, dz));
    const hits = await recordTruckHits(async hits => {
      await drive(driver, 40, { speed, onTick: () => hits.some(hit => hit.target.id === target.id) });
    });
    return hits.find(hit => hit.target.id === target.id);
  };
  const slow = await firstHit(0.3, truck.location.z - origin.z + 6);
  const fast = await firstHit(1, truck.location.z - origin.z + 12);
  if (!slow || !fast) throw new Error(`Moving truck failed to trample: slow=${slow?.damage} fast=${fast?.damage}`);
  if (!(fast.damage > slow.damage)) throw new Error(`Trample damage not speed-scaled: slow ${slow.damage}, fast ${fast.damage}`);
  checks.push(`trample damage scales with speed: ${slow.damage} at slow input, ${fast.damage} at full input`);
  return checks;
}

async function demolition({ dimension, origin, driver, run }) {
  const checks = [];
  // Parked beside planks: wood survives without momentum.
  fill(dimension, at(origin, -1, 5), at(origin, 1, 5, GROUND_Y + 1), "oak_planks");
  const truck = spawnTruck(dimension, run, at(origin, 0, 3));
  await wait(10);
  await board(driver, truck, 0);
  await wait(30);
  if (dimension.getBlock(at(origin, 0, 5)).typeId !== "minecraft:oak_planks") throw new Error("Parked truck demolished wood");
  checks.push("parked truck leaves wood intact");
  // Driven through a plank wall and a glass wall; stone stays.
  fill(dimension, at(origin, -2, 12), at(origin, 2, 12, GROUND_Y + 1), "oak_planks");
  fill(dimension, at(origin, -2, 20), at(origin, 2, 20, GROUND_Y + 1), "glass");
  fill(dimension, at(origin, 4, 12), at(origin, 4, 20, GROUND_Y + 1), "stone");
  truck.teleport(at(origin, 0, 1));
  await wait(5);
  await drive(driver, 50, { onTick: () => truck.location.z > origin.z + 26 });
  const plank = dimension.getBlock(at(origin, 0, 12)).typeId;
  const glass = dimension.getBlock(at(origin, 0, 20)).typeId;
  if (plank !== "minecraft:air" || glass !== "minecraft:air") throw new Error(`Wood Demolition failed: plank=${plank} glass=${glass}`);
  if (truck.location.z < origin.z + 22) throw new Error("Truck did not drive through the demolished walls");
  if (dimension.getBlock(at(origin, 4, 12)).typeId !== "minecraft:stone") throw new Error("Demolition destroyed stone");
  checks.push("driving through plank and glass walls demolishes them; stone untouched");
  return checks;
}

async function foliage_shearing({ dimension, origin, driver, run }) {
  const truck = spawnTruck(dimension, run, at(origin, 0, 3));
  await wait(10);
  await board(driver, truck, 0);
  fill(dimension, at(origin, -1, 4, GROUND_Y + 1), at(origin, 1, 5, GROUND_Y + 3), 'oak_leaves ["persistent_bit"=true]');
  await wait(20);
  const remaining = [];
  for (let x = -1; x <= 1; x++) for (let y = 1; y <= 3; y++) for (let z = 4; z <= 5; z++) {
    if (dimension.getBlock(at(origin, x, z, GROUND_Y + y)).typeId.includes("leaves")) remaining.push(`${x},${y},${z}`);
  }
  if (remaining.length) throw new Error("Foliage Shearing left leaves at rest: " + remaining.join(" "));
  return ["parked truck with a driver shears an overhanging canopy"];
}

async function dye_repaint({ dimension, origin, driver, run }) {
  const truck = spawnTruck(dimension, run, at(origin, 0, 3));
  await wait(10);
  if (truck.getProperty("blake:color") !== 0) throw new Error("Bare spawn must start red");
  driver.teleport(at(origin, -2, 3));
  driver.setItem(new ItemStack("minecraft:blue_dye", 3), 0, true);
  driver.isSneaking = true;
  await wait(4);
  driver.interactWithEntity(truck);
  await wait(6);
  driver.isSneaking = false;
  const color = truck.getProperty("blake:color");
  const left = driver.getComponent("minecraft:inventory").container.getItem(0)?.amount;
  if (color !== 1) throw new Error("Sneak-Dye Repainting did not paint blue: color " + color);
  if (left !== 3) throw new Error("Sneak-Dye Repainting consumed dye: " + left + " left");
  if (riders(truck).length) throw new Error("Sneak-dye interaction mounted the truck");
  return ["sneak-interact with blue dye repaints the truck blue", "dye not consumed and nobody mounted"];
}

async function retrieval({ dimension, origin, driver, run }) {
  const location = at(origin, 0, 6);
  const drops = () => {
    const totals = new Map();
    for (const item of dimension.getEntities({ type: "minecraft:item", location, maxDistance: 6 })) {
      const stack = item.getComponent("minecraft:item")?.itemStack;
      if (stack) totals.set(stack.typeId, (totals.get(stack.typeId) || 0) + stack.amount);
    }
    return totals;
  };
  const clear = () => dimension.getEntities({ type: "minecraft:item", location, maxDistance: 6 }).forEach(item => item.remove());
  const destroy = async (cause, damagingEntity) => {
    clear();
    const truck = spawnTruck(dimension, run, location);
    await wait(5);
    truck.applyDamage(5000, damagingEntity ? { cause, damagingEntity } : { cause });
    await wait(10);
    return drops();
  };
  const retrieved = await destroy(EntityDamageCause.entityAttack, driver);
  if (retrieved.get("blake:monster_truck_vehicle") !== 1 || retrieved.has("minecraft:iron_ingot")) {
    throw new Error("Player-fatal retrieval must return exactly one Vehicle Item: " + JSON.stringify([...retrieved]));
  }
  const checks = ["player-fatal dismantling returns exactly one Vehicle Item"];
  for (const cause of [EntityDamageCause.entityExplosion, EntityDamageCause.lava, EntityDamageCause.fire]) {
    const scrap = await destroy(cause);
    if ((scrap.get("minecraft:iron_ingot") || 0) < 1 || scrap.has("blake:monster_truck_vehicle")) {
      throw new Error(`${cause} destruction must drop Scrap only: ${JSON.stringify([...scrap])}`);
    }
  }
  clear();
  checks.push("explosion, lava, and fire destruction drop Scrap only");
  return checks;
}

async function incline_pitch({ dimension, origin, driver, run }) {
  const checks = [];
  for (const [rise, run_] of [[1, 2], [1, 3], [1, 1]]) {
    park(driver, origin);
    resetArena(dimension, origin);
    const steps = 10;
    const start = 4;
    const upEnd = start + steps * run_;
    const plateauEnd = upEnd + 6;
    for (let i = 1; i <= steps; i++) {
      // Up stairs, a 6-block plateau, then mirrored down stairs.
      fill(dimension, at(origin, -3, start + (i - 1) * run_), at(origin, 3, start + i * run_ - 1, GROUND_Y + i * rise - 1), "stone");
      fill(dimension, at(origin, -3, plateauEnd + (steps - i) * run_), at(origin, 3, plateauEnd + (steps - i + 1) * run_ - 1, GROUND_Y + i * rise - 1), "stone");
    }
    fill(dimension, at(origin, -3, upEnd), at(origin, 3, plateauEnd - 1, GROUND_Y + steps * rise - 1), "stone");
    const downEnd = plateauEnd + steps * run_;
    const truck = spawnTruck(dimension, run, at(origin, 0, 1));
    await wait(10);
    await board(driver, truck, 0);
    const up = [];
    const down = [];
    let previous = truck.getProperty("blake:pitch_angle");
    let maxStep = 0;
    await drive(driver, 160, {
      speed: 0.5,
      onTick: () => {
        const pitch = truck.getProperty("blake:pitch_angle");
        maxStep = Math.max(maxStep, Math.abs(pitch - previous));
        previous = pitch;
        const z = truck.location.z - origin.z;
        // Settled pitch: the second half of each flight of stairs, away from its ends.
        if (z > start + steps * run_ / 2 && z < upEnd - run_) up.push(pitch);
        if (z > plateauEnd + steps * run_ / 2 && z < downEnd - run_) down.push(pitch);
        return z > downEnd + 3;
      },
    });
    await wait(40);
    const settled = truck.getProperty("blake:pitch_angle");
    const expected = Math.min(PITCH_CLAMP, Math.atan2(rise, run_) * 180 / Math.PI);
    const mean = values => values.reduce((a, b) => a + b, 0) / Math.max(values.length, 1);
    const label = `${rise}:${run_} (expected ${expected.toFixed(1)}°)`;
    if (!up.length || !down.length) throw new Error(`${label}: truck did not traverse the ramp (z=${(truck.location.z - origin.z).toFixed(1)})`);
    if (Math.abs(mean(up) - expected) > PITCH_TOLERANCE) throw new Error(`${label}: uphill mean pitch ${mean(up).toFixed(1)}° ${JSON.stringify(up)}`);
    if (Math.abs(mean(down) + expected) > PITCH_TOLERANCE) throw new Error(`${label}: downhill mean pitch ${mean(down).toFixed(1)}° ${JSON.stringify(down)}`);
    if (settled !== 0) throw new Error(`${label}: pitch did not return to level on flat ground: ${settled}`);
    if (maxStep > PITCH_MAX_STEP) throw new Error(`${label}: pitch jumped ${maxStep}° in one tick`);
    checks.push(`${label}: uphill ${mean(up).toFixed(1)}°, downhill ${mean(down).toFixed(1)}°, level ${settled}°, max step ${maxStep}°/tick`);
    truck.remove();
    park(driver, origin);
    await wait(5);
  }
  return checks;
}

export const SCENARIOS = {
  smoke, seats, auto_step, suspension_jump, crush_stomp, shock_absorption,
  flotation_water, flotation_lava, trample, demolition, foliage_shearing,
  dye_repaint, retrieval, incline_pitch,
};
