import { Difficulty, Direction, EnchantmentType, GameMode, ItemStack, system, world, EntityDamageCause } from "@minecraft/server";
import { driverInput } from "../main.js";
import { DRIVING, headingVector } from "../driving.js";
import { HIT_COOLDOWN_TICKS } from "../contact.js";
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
const PITCH_SAMPLE_SPAN = 2.25;  // blocks between the front and rear ground samples (truck_tick.js, 1.125 each way)
const degrees = radians => radians * 180 / Math.PI;
// The Sixteen-Color Palette (CONTEXT.md); a color's position is its blake:color value.
const PALETTE = [
  "red", "blue", "green", "yellow", "black", "white", "orange", "magenta",
  "light_blue", "lime", "pink", "gray", "light_gray", "cyan", "purple", "brown",
];

// Accepted settled pitch on a stair ramp. Stairs are not a smooth slope: when one stair is
// longer than the sample span, the samples straddle a single step for part of each stair and
// read atan(rise / span) rather than the nominal angle. Both readings are correct (user, #38).
function pitchBand(rise, run_) {
  const readings = [degrees(Math.atan2(rise, run_))];
  if (run_ >= PITCH_SAMPLE_SPAN) readings.push(degrees(Math.atan2(rise, PITCH_SAMPLE_SPAN)));
  const low = Math.min(PITCH_CLAMP, Math.min(...readings)) - PITCH_TOLERANCE;
  const high = Math.min(PITCH_CLAMP, Math.max(...readings)) + PITCH_TOLERANCE;
  return { low, high };
}

const at = (origin, dx, dz, y = GROUND_Y) => ({ x: origin.x + dx, y, z: origin.z + dz });

// Record every hurt event caused by a truck while fn runs, with where the target and the truck
// were when it was hit.
async function recordTruckHits(fn) {
  const hits = [];
  const listener = world.afterEvents.entityHurt.subscribe(event => {
    const truck = event.damageSource.damagingEntity;
    if (truck?.typeId === "blake:monster_truck") {
      const target = event.hurtEntity;
      hits.push({
        target, typeId: target.typeId, damage: event.damage, cause: event.damageSource.cause,
        at: { ...target.location }, truckAt: { ...truck.location }, tick: system.currentTick,
      });
    }
  });
  try {
    await fn(hits);
  } finally {
    world.afterEvents.entityHurt.unsubscribe(listener);
  }
  return hits;
}

// One authoritative Tire Trample damage path: no target is hit twice by the same truck inside
// the hit cooldown (a second damage source would land in the same contact).
function assertNoDuplicateHits(hits, label) {
  for (const [i, hit] of hits.entries()) {
    const twin = hits.slice(i + 1).find(other => other.target.id === hit.target.id && other.tick - hit.tick < HIT_COOLDOWN_TICKS);
    if (twin) {
      throw new Error(`${label}: ${hit.typeId} hit twice within ${HIT_COOLDOWN_TICKS} ticks: ` +
        JSON.stringify([hit, twin].map(h => [h.tick, h.cause, h.damage])));
    }
  }
}

// Bystanders that Crush Stomp and Tire Trample must spare: another player (spawned once per
// scenario and parked until placed) and a wolf tamed to that player. The owner stands near the
// wolf: a tamed wolf teleports to an owner far away, which would carry it off the test spot.
function tamedWolf(dimension, owner, location) {
  const wolf = dimension.spawnEntity("minecraft:wolf", location);
  if (!wolf.getComponent("minecraft:tameable")?.tame(owner)) throw new Error("Could not tame the wolf to " + owner.name);
  // Slowness keeps the wolf from following its owner out of place.
  wolf.addEffect("slowness", 400, { amplifier: 255, showParticles: false });
  return wolf;
}

// Truck-sourced hits on, and health lost by, each bystander; empty when all were spared.
function bystanderHarm(hits, bystanders) {
  const harm = [];
  for (const { label, entity, before } of bystanders) {
    const taken = hits.filter(hit => hit.target.id === entity.id);
    const now = entity.isValid ? health(entity) : "gone";
    if (taken.length || now !== before) harm.push(`${label}: ${JSON.stringify(taken.map(h => [h.cause, h.damage]))} health ${before} -> ${now}`);
  }
  return harm;
}

// Deliberate exit: Sneak. A Simulated Driver sends no key presses, and setting isSneaking does
// not dismount it, so the sneaking rider is ejected; the add-on reads isSneaking to tell a
// deliberate exit from an engine detachment. The caller resets isSneaking.
async function sneakOut(truck, player) {
  player.isSneaking = true;
  await wait(1);
  const engineDismount = !riders(truck).some(rider => rider?.id === player.id);
  if (!engineDismount) truck.getComponent("minecraft:rideable").ejectRider(player);
  await wait(1);
  if (riders(truck).some(rider => rider?.id === player.id)) throw new Error(`${player.name} did not leave the truck`);
  return `${player.name} ${engineDismount ? "dismounted by sneaking" : "ejected while sneaking (sneak alone did not dismount)"}`;
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
  // Full forward input from the Passenger Seat must not drive the truck.
  const { movement } = driverInput;
  driverInput.movement = player => (player.id === passenger.id ? { x: 0, y: 1 } : movement(player));
  try {
    await wait(30);
  } finally {
    driverInput.movement = movement;
  }
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
    throw new Error(`Controlled Auto-Step launched the truck to +${(topY - GROUND_Y).toFixed(2)} on a 2-block ledge (launched instead of stepping up)`);
  }
  checks.push(`climbed a 2-block ledge while driven (reached +${(topY - GROUND_Y).toFixed(2)})`);
  truck.remove();
  park(driver, origin);
  await wait(5);
  // Three-block wall: beyond Controlled Auto-Step, so driving must not clear it.
  resetArena(dimension, origin);
  fill(dimension, at(origin, -3, 10), at(origin, 3, 10, GROUND_Y + 2), "stone");
  truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 30);
  if (truck.location.z > origin.z + 10) throw new Error("Truck drove over a 3-block wall");
  checks.push("a 3-block wall stops the truck");
  return checks;
}

const yawOf = truck => truck.getRotation().y;

// Signed angle (degrees) from the truck's heading to the direction it actually moved.
function slipAngle(truck, from) {
  const move = { x: truck.location.x - from.x, z: truck.location.z - from.z };
  if (Math.hypot(move.x, move.z) < 0.05) return 0;
  const head = headingVector(yawOf(truck));
  return Math.atan2(head.x * move.z - head.z * move.x, head.x * move.x + head.z * move.z) * 180 / Math.PI;
}

// Per-tick rider retention (#32): the driver must stay in the truck's rider list, keep its
// riding link, and stay at its seat offset on every tick.
function retentionTracker(truck, driver) {
  const offset = () => ({
    x: driver.location.x - truck.location.x,
    y: driver.location.y - truck.location.y,
    z: driver.location.z - truck.location.z,
  });
  const seat = offset();
  const lost = [];
  let maxDrift = 0;
  return {
    sample(tick) {
      const listed = riders(truck)[0]?.id === driver.id;
      const linked = driver.getComponent("minecraft:riding")?.entityRidingOn?.id === truck.id;
      const now = offset();
      const drift = Math.hypot(now.x - seat.x, now.y - seat.y, now.z - seat.z);
      maxDrift = Math.max(maxDrift, drift);
      if (!listed || !linked) lost.push({ tick, listed, linked, y: +(truck.location.y - GROUND_Y).toFixed(2) });
    },
    verify(label) {
      if (lost.length) throw new Error(`${label}: driver detached on ${lost.length} ticks ${JSON.stringify(lost.slice(0, 8))}`);
      if (maxDrift > 1) throw new Error(`${label}: driver drifted ${maxDrift.toFixed(2)} blocks from the seat`);
      return `${label}: driver seated and linked every tick (max seat drift ${maxDrift.toFixed(2)} blocks)`;
    },
  };
}

async function steering({ dimension, origin, driver, run }) {
  const checks = [];
  // Parked: A turns the front wheels fully but the truck does not spin in place.
  let truck = spawnTruck(dimension, run, at(origin, 0, 4));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 15, { forward: 0, strafe: 1 });
  const parkedSteer = truck.getProperty("blake:steer_angle");
  if (parkedSteer !== -26) throw new Error("A did not turn the parked truck's wheels fully left: " + parkedSteer);
  if (Math.abs(yawOf(truck)) > 0.5) throw new Error("Parked truck spun in place: yaw " + yawOf(truck));
  await drive(driver, 10, { forward: 0 });
  if (truck.getProperty("blake:steer_angle") !== 0) throw new Error("Wheels did not spring back to center");
  checks.push("parked: A turns the wheels fully (-26), truck holds its heading, wheels re-center on release");

  // The mouse only moves the camera: turning the driver does not steer the truck.
  driver.setBodyRotation(90);
  const start = truck.location;
  await drive(driver, 20);
  if (Math.abs(yawOf(truck)) > 0.5) throw new Error("Driver look direction steered the truck: yaw " + yawOf(truck));
  if (truck.location.z - start.z < 5 || Math.abs(truck.location.x - start.x) > 0.5) {
    throw new Error(`Truck did not drive straight ahead: dx ${(truck.location.x - start.x).toFixed(2)} dz ${(truck.location.z - start.z).toFixed(2)}`);
  }
  checks.push("driver looking sideways: the truck keeps driving straight (mouse does not steer)");
  truck.remove();
  driver.setBodyRotation(0);

  // While driving, A turns left (toward +X when facing +Z) and D turns right.
  for (const [strafe, key] of [[1, "A"], [-1, "D"]]) {
    park(driver, origin);
    resetArena(dimension, origin);
    truck = spawnTruck(dimension, run, at(origin, 0, -4));
    await wait(10);
    await board(driver, truck, 0);
    await drive(driver, 20, { forward: 0.5 });
    const before = { ...truck.location, yaw: yawOf(truck) };
    await drive(driver, 20, { forward: 0.5, strafe });
    const turned = yawOf(truck) - before.yaw;
    const sideways = truck.location.x - before.x;
    const left = strafe > 0;
    if (left ? turned > -30 : turned < 30) throw new Error(`${key} turned the truck ${turned.toFixed(1)} degrees`);
    if (left ? sideways < 2 : sideways > -2) throw new Error(`${key} moved the truck ${sideways.toFixed(2)} blocks sideways`);
    checks.push(`${key} while driving turns ${left ? "left" : "right"}: yaw ${turned.toFixed(1)} degrees, ${sideways.toFixed(1)} blocks along X`);
    truck.remove();
  }
  return checks;
}

async function handbrake({ dimension, origin, driver, run }) {
  const checks = [];
  // Straight line: from cruising speed the handbrake stops the truck hard, without turning.
  let truck = spawnTruck(dimension, run, at(origin, 0, -4));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 30);
  let last = truck.location;
  let stopTick;
  await drive(driver, 40, {
    forward: 0,
    handbrake: true,
    onTick: tick => {
      const moved = horizontal(truck.location, last);
      last = truck.location;
      if (stopTick === undefined && moved < 0.01) stopTick = tick;
      return false;
    },
  });
  if (stopTick === undefined || stopTick > 30) throw new Error("Handbrake did not stop the truck within 1.5 s");
  if (Math.abs(yawOf(truck)) > 0.5) throw new Error("Straight handbrake stop turned the truck: yaw " + yawOf(truck));
  checks.push(`straight handbrake stop from speed in ${stopTick} ticks without turning`);
  const parkedAt = truck.location;
  await drive(driver, 20, { forward: 1, handbrake: true });
  if (horizontal(truck.location, parkedAt) > 0.1) throw new Error("Truck crept forward with the handbrake held");
  checks.push("handbrake held: W does not move a parked truck");
  truck.remove();

  // Drift: steering with the handbrake held at speed swings the rear out; release regains grip.
  park(driver, origin);
  resetArena(dimension, origin);
  truck = spawnTruck(dimension, run, at(origin, 0, -4));
  await wait(10);
  await board(driver, truck, 0);
  await drive(driver, 30);
  const tracker = retentionTracker(truck, driver);
  let maxSlip = 0;
  last = truck.location;
  const yawBefore = yawOf(truck);
  await drive(driver, 12, {
    forward: 1,
    strafe: -1,
    handbrake: true,
    onTick: tick => {
      tracker.sample(tick);
      maxSlip = Math.max(maxSlip, Math.abs(slipAngle(truck, last)));
      last = truck.location;
      return false;
    },
  });
  const driftTurn = yawOf(truck) - yawBefore;
  if (maxSlip < 10) throw new Error(`Handbrake turn did not slide: max slip ${maxSlip.toFixed(1)} degrees`);
  checks.push(`handbrake drift: truck turned ${driftTurn.toFixed(1)} degrees while sliding up to ${maxSlip.toFixed(1)} degrees off its heading`);
  let finalSlip = 0;
  await drive(driver, 12, {
    forward: 1,
    onTick: tick => {
      tracker.sample(12 + tick);
      finalSlip = slipAngle(truck, last);
      last = truck.location;
      return false;
    },
  });
  if (Math.abs(finalSlip) > 3) throw new Error(`Grip did not return after release: slip ${finalSlip.toFixed(1)} degrees`);
  checks.push(`grip regained within 0.6 s of release (slip ${finalSlip.toFixed(1)} degrees)`);
  checks.push(tracker.verify("handbrake drift"));
  return checks;
}

// Crush Stomp reaches every entity within this distance of the landing (landing.js).
const CRUSH_STOMP_RADIUS = 3.5;

async function crush_stomp({ dimension, origin, driver, run, spawnPlayer }) {
  const checks = [];
  const bystander = spawnPlayer("SimulatedBystander");
  await wait(10);
  for (const height of [4, 2]) {
    park(driver, origin);
    park(bystander, origin);
    resetArena(dimension, origin);
    // A ledge of the given height; drive off it slowly and land on a mob placed beneath the
    // truck just before touchdown, so no Tire Trample hit precedes the landing.
    fill(dimension, at(origin, -4, 0), at(origin, 4, 8, GROUND_Y + height - 1), "stone");
    const top = GROUND_Y + height;
    const truck = spawnTruck(dimension, run, at(origin, 0, 3, top));
    const stomping = height >= 3;
    // On the stomping drop, a tamed wolf, another player, and a parked truck stand inside the
    // Crush Stomp radius beside the landing; they wait clear of the ledge until placed.
    const wolf = stomping ? tamedWolf(dimension, bystander, at(origin, -8, -4)) : undefined;
    await wait(10);
    await board(driver, truck, 0);
    let placed = false;
    const bystanders = [];
    const hits = await recordTruckHits(async () => {
      await drive(driver, 40, {
        forward: 0.3,
        onTick: () => {
          if (!placed && truck.location.y < GROUND_Y + 1.5) {
            placed = true;
            const t = truck.location;
            dimension.spawnEntity("minecraft:zombie", { x: t.x, y: GROUND_Y, z: t.z });
            if (stomping) {
              wolf.teleport({ x: t.x + 2.3, y: GROUND_Y, z: t.z });
              bystander.teleport({ x: t.x + 2.3, y: GROUND_Y, z: t.z + 2 });
              const parked = spawnTruck(dimension, run, { x: t.x - 3.0, y: GROUND_Y, z: t.z + 0.5 });
              bystanders.push(
                { label: "tamed wolf", entity: wolf, before: health(wolf) },
                { label: "bystander player", entity: bystander, before: health(bystander) },
                { label: "parked truck", entity: parked, before: health(parked) });
            }
          }
          const landed = placed && truck.location.y < GROUND_Y + 0.05;
          // Crush Stomp measures its radius from the truck at touchdown; the shockwave's impulse
          // only moves them on a later tick.
          if (landed) {
            for (const bystander of bystanders) {
              bystander.atLanding = bystander.entity.isValid ? horizontal(bystander.entity.location, truck.location) : Infinity;
            }
          }
          return landed;
        },
      });
      await wait(10);
    });
    if (!placed) throw new Error(`Truck never drove off the ${height}-block ledge`);
    // Crush Stomp deals contact damage; Tire Trample deals entity-attack damage.
    const crush = hits.find(hit => hit.typeId === "minecraft:zombie" && hit.cause === EntityDamageCause.contact);
    if (height >= 3 && !crush) throw new Error(`${height}-block drop did not Crush Stomp the mob beneath: ${JSON.stringify(hits.map(h => [h.cause, h.damage]))}`);
    if (crush && crush.damage < 60) throw new Error("Crush Stomp damage below lethal threshold: " + crush.damage);
    if (height < 3 && crush) throw new Error(`${height}-block drop Crush Stomped (drops under 3 blocks must not)`);
    if (health(driver) !== PLAYER_MAX_HEALTH) throw new Error("Driver was hurt by the landing: " + health(driver));
    const harm = bystanderHarm(hits, bystanders);
    if (harm.length) throw new Error(`${height}-block Crush Stomp hurt a protected bystander: ${harm.join("; ")}`);
    // Every bystander must have been inside the radius at touchdown, or sparing it proves nothing.
    for (const { label, atLanding } of bystanders) {
      if (!(atLanding < CRUSH_STOMP_RADIUS)) throw new Error(`${label} was ${atLanding?.toFixed(2)} blocks from the landing, outside the Crush Stomp radius`);
    }
    checks.push(stomping
      ? `${height}-block drop: Crush Stomp dealt ${crush.damage} damage to the mob beneath; driver unhurt`
      : `${height}-block drop: no Crush Stomp`);
    if (stomping) {
      checks.push(`${height}-block drop: a tamed wolf, another player, and a parked truck inside the radius ` +
        `(${bystanders.map(b => b.atLanding.toFixed(2)).join(", ")} blocks at touchdown) were not hit and lost no health`);
    }
  }
  return checks;
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

// Pneumatic Shock Absorption with both seats taken, then a deliberate Sneak exit inside the
// landing's protection window: fall damage to the rider who left must land at once, while the
// rider still seated is protected at the same tick; later on-foot falls hurt both (no leak).
async function two_seat_drop({ dimension, origin, driver, run, spawnPlayer }) {
  const checks = [];
  const height = 8;
  fill(dimension, at(origin, -4, 0), at(origin, 4, 8, GROUND_Y + height - 1), "stone");
  const truck = spawnTruck(dimension, run, at(origin, 0, 3, GROUND_Y + height));
  await wait(10);
  await board(driver, truck, 0);
  const passenger = spawnPlayer("SimulatedPassenger");
  await wait(10);
  await board(passenger, truck, 1);
  let landedAt;
  await drive(driver, 60, {
    forward: 0.3,
    onTick: () => {
      if (truck.isOnGround && truck.location.y < GROUND_Y + 0.05) landedAt = system.currentTick;
      return landedAt !== undefined;
    },
  });
  if (landedAt === undefined) throw new Error(`Truck never landed after the ${height}-block drop: y=${(truck.location.y - GROUND_Y).toFixed(2)}`);
  await wait(1);
  const seated = riders(truck).map(rider => rider?.id);
  if (seated[0] !== driver.id || seated[1] !== passenger.id) throw new Error("Riders were not kept seated through the drop");
  const healths = { truck: health(truck), driver: health(driver), passenger: health(passenger) };
  if (healths.truck !== TRUCK_MAX_HEALTH || healths.driver !== PLAYER_MAX_HEALTH || healths.passenger !== PLAYER_MAX_HEALTH) {
    throw new Error(`${height}-block drop caused fall damage: ${JSON.stringify(healths)}`);
  }
  checks.push(`${height}-block drop with both seats taken: truck ${healths.truck}/${TRUCK_MAX_HEALTH}, ` +
    `driver and passenger ${PLAYER_MAX_HEALTH}/${PLAYER_MAX_HEALTH}, both still seated`);

  // Deliberate exit by Sneak (sneakOut).
  const passengerExit = await sneakOut(truck, passenger);
  // Inside the landing window: fall damage to the passenger who left must land; to the driver
  // still seated it must be cancelled (the control showing the window is still open).
  const before = { driver: health(driver), passenger: health(passenger) };
  const fall = { cause: EntityDamageCause.fall };
  passenger.applyDamage(4, fall);
  driver.applyDamage(4, fall);
  const probeTick = system.currentTick - landedAt;
  await wait(1);
  const hurt = { driver: health(driver), passenger: health(passenger) };
  if (!(hurt.driver === before.driver)) throw new Error(`Seated driver not protected ${probeTick} ticks after landing: ${JSON.stringify(hurt)}`);
  if (!(hurt.passenger < before.passenger)) {
    throw new Error(`Fall protection leaked after the Sneak exit: passenger took no fall damage ${probeTick} ticks after landing ${JSON.stringify(hurt)}`);
  }
  checks.push(`${passengerExit}; ${probeTick} ticks after landing, 4 fall damage hurt the passenger who left ` +
    `(${before.passenger} -> ${hurt.passenger}) and was cancelled for the driver still seated (${hurt.driver})`);

  const driverExit = await sneakOut(truck, driver);
  for (const player of [driver, passenger]) player.isSneaking = false;
  checks.push("Sneak exit: " + driverExit);

  // Unrelated falls, clear of the truck and the mesa: 6 blocks onto open ground.
  const standing = { driver: health(driver), passenger: health(passenger) };
  driver.teleport(at(origin, -8, 2, GROUND_Y + 6));
  passenger.teleport(at(origin, -8, 6, GROUND_Y + 6));
  await wait(40);
  const after = { driver: health(driver), passenger: health(passenger) };
  if (!(after.driver < standing.driver) || !(after.passenger < standing.passenger)) {
    throw new Error(`Fall protection leaked after the Sneak exit: ${JSON.stringify({ standing, after })}`);
  }
  checks.push(`after exiting, a 6-block on-foot fall hurts: driver ${standing.driver} -> ${after.driver}, passenger ${standing.passenger} -> ${after.passenger}`);
  return checks;
}

async function liquid_crossing({ dimension, origin, driver, run }, liquid) {
  // Liquid pool flush with the ground, then a long 1-block-high bank that doubles as the
  // overland reference lane: the truck must cross liquid at full overland cruising speed.
  fill(dimension, at(origin, -5, 6, GROUND_Y - 3), at(origin, 5, 40, GROUND_Y - 1), liquid);
  fill(dimension, at(origin, -5, 41, GROUND_Y), at(origin, 5, 79, GROUND_Y), "stone");
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  let lowest = Infinity;
  let poolTicks = 0;
  let landTicks = 0;
  let steppedUp = false;
  const trace = [];
  await drive(driver, 200, {
    onTick: tick => {
      const z = truck.location.z - origin.z;
      if (z > 35) trace.push([tick, +z.toFixed(2), +(truck.location.y - GROUND_Y).toFixed(2), +truck.getVelocity().y.toFixed(2)]);
      // Measured after the truck reaches cruising speed (~1.5 s from rest).
      if (z > 9 && z < 38) lowest = Math.min(lowest, truck.location.y);
      if (z > 19 && z < 38) poolTicks++;
      if (z > 43 && z < 48 && truck.location.y >= GROUND_Y + 0.9) steppedUp = true;
      if (z > 52 && z < 71) landTicks++;
      return z > 74;
    },
  });
  const checks = [];
  if (lowest < GROUND_Y - 1.5) throw new Error(`Truck sank in ${liquid}: lowest y ${(lowest - GROUND_Y).toFixed(2)}`);
  checks.push(`floated across ${liquid} (lowest ${(lowest - GROUND_Y).toFixed(2)} relative to the surface)`);
  if (!steppedUp) {
    throw new Error(`Shoreline Step-Up failed: z=${(truck.location.z - origin.z).toFixed(1)} y=${(truck.location.y - GROUND_Y).toFixed(2)} ` +
      `[tick, z, y, vy] ${JSON.stringify(trace.slice(0, 40))}`);
  }
  checks.push("Shoreline Step-Up onto a 1-block bank without a jump");
  if (!landTicks) throw new Error(`Truck never drove the overland lane: z=${(truck.location.z - origin.z).toFixed(1)}`);
  const poolSpeed = 19 / Math.max(poolTicks, 1);
  const landSpeed = 19 / landTicks;
  const speeds = `${liquid} ${poolSpeed.toFixed(2)} vs overland ${landSpeed.toFixed(2)} blocks/tick`;
  // 10% allows for tick-boundary counting over a 19-block window.
  if (poolSpeed < 0.9 * landSpeed) throw new Error(`Not crossing ${liquid} at overland cruising speed: ${speeds}`);
  checks.push(`crossed ${liquid} at overland cruising speed: ${speeds}`);
  if (riders(truck)[0]?.id !== driver.id) throw new Error("Driver lost the seat while crossing " + liquid);
  return { truck, checks };
}

async function flotation_water(context) {
  return (await liquid_crossing(context, "water")).checks;
}

async function flotation_lava(context) {
  const { dimension, origin, driver } = context;
  const { truck, checks } = await liquid_crossing(context, "lava");
  if (health(driver) !== PLAYER_MAX_HEALTH || driver.getComponent("minecraft:onfire")) {
    throw new Error(`Rider not shielded from lava: health ${health(driver)}`);
  }
  checks.push("rider shielded from lava heat");
  // Molten Tire Trample: a heavy mob survives the hit, so ignition is observable.
  const golem = dimension.spawnEntity("minecraft:iron_golem", at(origin, 0, Math.min(77, truck.location.z - origin.z + 6), GROUND_Y + 1));
  await wait(5);
  await drive(driver, 20, { onTick: () => golem.getComponent("minecraft:onfire") !== undefined });
  if (!golem.isValid || !golem.getComponent("minecraft:onfire")) throw new Error("Molten Tire Trample did not ignite the mob");
  checks.push("Molten Tire Trample ignited a mob after leaving lava");
  return checks;
}

// Amphibious Flotation from rest: a truck floating still in the liquid starts on W, follows A/D,
// and once input is released gets no further push and coasts to a stop.
async function liquid_from_rest({ dimension, origin, driver, run }, liquid) {
  const checks = [];
  fill(dimension, at(origin, -11, 0, GROUND_Y - 3), at(origin, 11, 78, GROUND_Y - 1), liquid);
  // Start left of center (A turns toward +X), beside a stone pier to board from.
  fill(dimension, at(origin, -7, 1, GROUND_Y - 3), at(origin, -6, 5, GROUND_Y - 1), "stone");
  const truck = spawnTruck(dimension, run, at(origin, -4, 3));
  await wait(30);
  await board(driver, truck, 0, at(origin, -6, 3));
  const inLiquid = () => dimension.getBlock(truck.location)?.typeId === `minecraft:${liquid}`;

  let start = truck.location;
  await drive(driver, 20, { forward: 0 });
  const idleDrift = horizontal(truck.location, start);
  if (!inLiquid()) throw new Error(`Truck is not floating in ${liquid}: y=${(truck.location.y - GROUND_Y).toFixed(2)}`);
  if (idleDrift > 0.1) throw new Error(`Truck was not at rest in ${liquid}: drifted ${idleDrift.toFixed(2)} blocks in 20 idle ticks`);
  start = truck.location;
  await drive(driver, 20, { forward: 0.6 });
  const ahead = truck.location.z - start.z;
  if (ahead < 2) throw new Error(`W from rest in ${liquid} moved the truck only ${ahead.toFixed(2)} blocks forward in 20 ticks`);
  if (!inLiquid()) throw new Error(`Truck left the ${liquid} while starting`);
  checks.push(`${liquid}: at rest (${idleDrift.toFixed(3)} blocks drift in 20 idle ticks), W moved it ${ahead.toFixed(1)} blocks forward in 20 ticks`);

  for (const [strafe, key] of [[1, "A"], [-1, "D"]]) {
    const yawBefore = yawOf(truck);
    await drive(driver, 12, { forward: 0.6, strafe });
    const turned = yawOf(truck) - yawBefore;
    if (strafe > 0 ? turned > -10 : turned < 10) throw new Error(`${key} in ${liquid} turned the truck ${turned.toFixed(1)} degrees`);
    // Then straight on: once the wheels re-center, propulsion follows the new heading. Measured
    // over the last 5 ticks, when the heading no longer changes within a tick.
    await drive(driver, 7, { forward: 0.6 });
    const from = truck.location;
    await drive(driver, 5, { forward: 0.6 });
    const slip = slipAngle(truck, from);
    if (Math.abs(slip) > 3) throw new Error(`After ${key} in ${liquid}: motion ${slip.toFixed(1)} degrees off the heading`);
    if (!inLiquid()) throw new Error(`Truck left the ${liquid} while steering`);
    checks.push(`${liquid}: ${key} turned the truck ${turned.toFixed(1)} degrees in 12 ticks; ` +
      `then moving ${slip.toFixed(1)} degrees off its new heading`);
  }

  const speeds = [];
  let last = truck.location;
  await drive(driver, 60, {
    forward: 0,
    onTick: () => {
      speeds.push(horizontal(truck.location, last));
      last = truck.location;
      return false;
    },
  });
  // Per-tick distance in a liquid is noisy (lava: one tick can cover 0.14 blocks more than the
  // one before while the commanded coast speed falls), so the decay is judged on 5-tick means.
  const trace = JSON.stringify(speeds.map(speed => +speed.toFixed(3)));
  const means = [];
  for (let i = 0; i + 5 <= speeds.length; i += 5) means.push(speeds.slice(i, i + 5).reduce((a, b) => a + b, 0) / 5);
  const stopped = means.findIndex(mean => mean < 0.01);
  if (stopped < 0) throw new Error(`Truck did not stop within 60 ticks of releasing input in ${liquid}: ${trace}`);
  for (let i = 1; i <= stopped; i++) {
    if (!(means[i] < means[i - 1])) throw new Error(`Released input in ${liquid} still pushed the truck: ${trace}`);
  }
  if (means.slice(stopped).some(mean => mean >= 0.01)) throw new Error(`Truck moved again after stopping in ${liquid}: ${trace}`);
  checks.push(`${liquid}: released at ${speeds[0].toFixed(2)} blocks/tick; 5-tick mean speed fell every window ` +
    `(${means.slice(0, stopped + 1).map(mean => mean.toFixed(3)).join(" > ")}) and stayed below 0.01 from tick ${stopped * 5}`);
  if (riders(truck)[0]?.id !== driver.id) throw new Error(`Driver lost the seat in ${liquid}`);
  return checks;
}

async function liquid_start_water(context) {
  return liquid_from_rest(context, "water");
}

async function liquid_start_lava(context) {
  const { driver } = context;
  const checks = await liquid_from_rest(context, "lava");
  if (health(driver) !== PLAYER_MAX_HEALTH || driver.getComponent("minecraft:onfire")) {
    throw new Error(`Rider not shielded in lava: health ${health(driver)}, on fire ${Boolean(driver.getComponent("minecraft:onfire"))}`);
  }
  checks.push(`lava: rider at ${PLAYER_MAX_HEALTH}/${PLAYER_MAX_HEALTH} health and not burning`);
  return checks;
}

// Shoreline Step-Up out of water and lava onto banks flush with, 1 and 2 blocks above the
// surface (bank height counts above the liquid surface), without a jump: up on the bank within
// 20 ticks (1 s) of reaching it, never more than 0.5 above its top (climbed, not launched).
async function shoreline_step({ dimension, origin, driver, run }) {
  const checks = [];
  for (const liquid of ["water", "lava"]) {
    for (const height of [0, 1, 2]) {
      park(driver, origin);
      resetArena(dimension, origin);
      await wait(5);
      fill(dimension, at(origin, -5, 6, GROUND_Y - 3), at(origin, 5, 40, GROUND_Y - 1), liquid);
      if (height > 0) fill(dimension, at(origin, -5, 41, GROUND_Y), at(origin, 5, 79, GROUND_Y + height - 1), "stone");
      const truck = spawnTruck(dimension, run, at(origin, 0, 2));
      await wait(10);
      await board(driver, truck, 0);
      let topY = -Infinity;
      let contact;
      let up;
      const trace = [];
      await drive(driver, 160, {
        onTick: tick => {
          const z = truck.location.z - origin.z;
          const y = truck.location.y - GROUND_Y;
          if (z > 35) trace.push([tick, +z.toFixed(2), +y.toFixed(2)]);
          // Reaching the bank: the truck's 2.25-wide box at the face (z 40.5), or already lifting.
          if (contact === undefined && z > 33 && (z >= 39.3 || y > 0.05)) contact = tick;
          if (up === undefined && z > 40.6 && y >= height - 0.1) up = tick;
          if (contact !== undefined) topY = Math.max(topY, y);
          return z > 55;
        },
      });
      const label = `${liquid}, bank ${height} above the surface`;
      const fail = message => new Error(`${label}: ${message} [tick, z, y] ${JSON.stringify(trace.slice(0, 40))}`);
      if (contact === undefined || up === undefined) throw fail(`never got up on the bank (contact ${contact}, up ${up})`);
      const ticks = up - contact;
      const peak = topY - height;
      if (ticks > 20) throw fail(`took ${ticks} ticks from reaching the bank to being on it`);
      if (peak > 0.5) throw fail(`launched to +${peak.toFixed(2)} over the bank top`);
      if (truck.location.z - origin.z < 55) throw fail("did not drive on along the bank");
      if (riders(truck)[0]?.id !== driver.id) throw new Error(`${label}: driver lost the seat`);
      if (health(driver) !== PLAYER_MAX_HEALTH) throw new Error(`${label}: rider hurt, health ${health(driver)}`);
      checks.push(`${label}: on the bank ${ticks} ticks after reaching it, peak +${peak.toFixed(2)} over its top; rider unhurt`);
      truck.remove();
    }
  }
  return checks;
}

// A continuous wall 3 blocks above the liquid surface is not a shoreline: driving into it from
// water or lava never lifts the truck, which stays afloat against it.
async function shoreline_wall({ dimension, origin, driver, run }) {
  const checks = [];
  const height = 3;
  for (const liquid of ["water", "lava"]) {
    park(driver, origin);
    resetArena(dimension, origin);
    await wait(5);
    fill(dimension, at(origin, -5, 6, GROUND_Y - 3), at(origin, 5, 40, GROUND_Y - 1), liquid);
    fill(dimension, at(origin, -5, 41, GROUND_Y), at(origin, 5, 79, GROUND_Y + height - 1), "stone");
    const truck = spawnTruck(dimension, run, at(origin, 0, 2));
    await wait(10);
    await board(driver, truck, 0);
    let topY = -Infinity;
    let pushed = 0;
    await drive(driver, 100, {
      onTick: () => {
        topY = Math.max(topY, truck.location.y);
        if (truck.location.z - origin.z > 38) pushed++;
        return false;
      },
    });
    const z = truck.location.z - origin.z;
    const rise = topY - GROUND_Y;
    const floating = dimension.getBlock(truck.location)?.typeId === `minecraft:${liquid}`;
    const label = `${liquid}, ${height}-block wall`;
    if (pushed < 20) throw new Error(`${label}: truck never drove up against the wall (z=${z.toFixed(1)})`);
    if (z > 41 || rise > 1 || !floating) {
      throw new Error(`${label}: truck climbed or left the liquid: z=${z.toFixed(1)} top +${rise.toFixed(2)} floating=${floating}`);
    }
    if (riders(truck)[0]?.id !== driver.id) throw new Error(`${label}: driver lost the seat`);
    checks.push(`${label}: driven into it for ${pushed} ticks, not climbed; truck afloat at z=${z.toFixed(1)}, ` +
      `never above +${rise.toFixed(2)}`);
    truck.remove();
  }
  return checks;
}

async function trample({ dimension, origin, driver, run, spawnPlayer }) {
  const checks = [];
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  // Parked: a mob touching the tires is unharmed.
  const parkedAt = truck.location;
  const parkedHits = await recordTruckHits(async () => {
    dimension.spawnEntity("minecraft:pig", at(origin, 1.5, 2));
    await wait(30);
  });
  if (parkedHits.length) throw new Error("Parked truck damaged a mob: " + JSON.stringify(parkedHits.map(hit => [hit.cause, hit.damage])));
  checks.push(`parked truck (moved ${horizontal(truck.location, parkedAt).toFixed(3)} blocks) dealt no damage to a pig at its tires for 30 ticks`);
  truck.remove();

  // Low, medium, and high speed: each run starts from rest with a fresh pig 26 blocks ahead, so
  // the truck has reached its speed and the hit is the pig's first (bedrock-physics.md: the
  // immunity window). The pig stands 1.5 blocks to the truck's left (+X), so outward knockback
  // has a sideways component that a straight-ahead shove lacks.
  const runs = [];
  for (const forward of [0.3, 0.6, 1]) {
    park(driver, origin);
    resetArena(dimension, origin);
    const runner = spawnTruck(dimension, run, at(origin, 0, -4));
    await wait(10);
    await board(driver, runner, 0);
    const pig = dimension.spawnEntity("minecraft:pig", at(origin, 1.5, 22));
    // Slowness keeps the pig from wandering out of the truck's path; knockback still moves it.
    pig.addEffect("slowness", 200, { amplifier: 255, showParticles: false });
    let last = runner.location;
    let speed = 0;
    const hits = await recordTruckHits(async hits => {
      await drive(driver, 120, {
        forward,
        onTick: () => {
          if (hits.some(hit => hit.target.id === pig.id)) return true;
          speed = horizontal(runner.location, last);
          last = runner.location;
          return false;
        },
      });
      // Knockback is an impulse the engine applies on its next move, so it shows as displacement.
      await wait(2);
    });
    assertNoDuplicateHits(hits, `input ${forward}`);
    const hit = hits.find(entry => entry.target.id === pig.id);
    if (!hit) {
      throw new Error(`Truck at input ${forward} never trampled the pig: truck z=${(runner.location.z - origin.z).toFixed(1)}, ` +
        `pig ${pig.isValid ? `at (${(pig.location.x - origin.x).toFixed(1)}, ${(pig.location.z - origin.z).toFixed(1)})` : "gone"}`);
    }
    if (hit.cause !== EntityDamageCause.entityAttack) throw new Error(`Tire Trample hit had cause ${hit.cause}`);
    const intended = DRIVING.topSpeed * forward;
    if (Math.abs(speed - intended) > 0.15 * intended) {
      throw new Error(`Truck at input ${forward} hit at ${speed.toFixed(3)} blocks/tick, not its driven speed ${intended.toFixed(3)}`);
    }
    const outward = { x: hit.at.x - hit.truckAt.x, z: hit.at.z - hit.truckAt.z };
    if (!pig.isValid) throw new Error(`Pig vanished before its knockback could be measured (input ${forward})`);
    const v = { x: pig.location.x - hit.at.x, y: pig.location.y - hit.at.y, z: pig.location.z - hit.at.z };
    if (!(Math.sign(v.x) === Math.sign(outward.x) && v.x * outward.x + v.z * outward.z > 0 && v.y > 0)) {
      throw new Error(`Knockback at input ${forward} not outward: moved ${JSON.stringify(v)} in 2 ticks, outward ${JSON.stringify(outward)}`);
    }
    runs.push({ forward, speed, damage: hit.damage, v, outward });
    runner.remove();
  }
  for (let i = 1; i < runs.length; i++) {
    if (!(runs[i].damage > runs[i - 1].damage)) {
      throw new Error("Trample damage not strictly increasing with speed: " +
        runs.map(r => `${r.speed.toFixed(2)} b/t -> ${r.damage}`).join(", "));
    }
  }
  checks.push("trample damage rises with measured speed: " +
    runs.map(r => `input ${r.forward}: ${r.speed.toFixed(2)} blocks/tick -> ${r.damage}`).join("; "));
  checks.push("knockback throws the pig up and away from the truck (2-tick displacement for pig offset from truck): " + runs.map(r =>
    `(${r.v.x.toFixed(2)}, ${r.v.y.toFixed(2)}, ${r.v.z.toFixed(2)}) for (${r.outward.x.toFixed(2)}, ${r.outward.z.toFixed(2)})`).join("; "));

  // Exclusions: one full-speed pass through a pig (the control: Tire Trample is live), then a
  // tamed wolf, another player, and a parked truck in the truck's path.
  const bystanderPlayer = spawnPlayer("SimulatedBystander");
  park(driver, origin);
  resetArena(dimension, origin);
  const runner = spawnTruck(dimension, run, at(origin, 0, -4));
  await wait(10);
  await board(driver, runner, 0);
  const pig = dimension.spawnEntity("minecraft:pig", at(origin, 1.5, 12));
  pig.addEffect("slowness", 200, { amplifier: 255, showParticles: false });
  bystanderPlayer.teleport(at(origin, 1.5, 24));
  const wolfSpot = at(origin, -1.5, 18);
  const wolf = tamedWolf(dimension, bystanderPlayer, wolfSpot);
  const parked = spawnTruck(dimension, run, at(origin, 0, 32));
  await wait(5);
  if (horizontal(wolf.location, wolfSpot) > 1) {
    throw new Error(`Tamed wolf left its spot in the truck's path: now ${horizontal(wolf.location, wolfSpot).toFixed(2)} blocks away`);
  }
  const bystanders = [
    { label: "tamed wolf", entity: wolf, before: health(wolf), closest: Infinity },
    { label: "bystander player", entity: bystanderPlayer, before: health(bystanderPlayer), closest: Infinity },
    { label: "parked truck", entity: parked, before: health(parked), closest: Infinity },
  ];
  const hits = await recordTruckHits(async () => {
    await drive(driver, 80, {
      onTick: () => {
        for (const bystander of bystanders) {
          if (bystander.entity.isValid) bystander.closest = Math.min(bystander.closest, horizontal(runner.location, bystander.entity.location));
        }
        return runner.location.z > origin.z + 29;
      },
    });
    await wait(4);
  });
  assertNoDuplicateHits(hits, "exclusion pass");
  if (!hits.some(hit => hit.target.id === pig.id && hit.cause === EntityDamageCause.entityAttack)) {
    throw new Error("Exclusion pass: the control pig was not trampled, so the pass proves nothing");
  }
  const harm = bystanderHarm(hits, bystanders);
  if (harm.length) throw new Error(`Tire Trample hurt a protected bystander: ${harm.join("; ")}`);
  // Spared only counts if within reach: the wolf and the player in the truck's 2.25-wide path
  // (pig hits land at 1.5 off center), the parked truck in a collision (2.25 apart).
  for (const { label, closest } of bystanders) {
    const reach = label === "parked truck" ? 2.6 : 1.6;
    if (!(closest <= reach)) throw new Error(`Exclusion pass: truck came no closer than ${closest.toFixed(2)} blocks to the ${label}`);
  }
  checks.push("full-speed pass: trampled the control pig, then drove through a tamed wolf, another player, and into a parked truck " +
    `(closest ${bystanders.map(b => b.closest.toFixed(2)).join(", ")} blocks) with no hit and no health lost`);
  checks.push(`no target hit twice by a truck within ${HIT_COOLDOWN_TICKS} ticks in the full-speed pass, ` +
    "nor within the 2 ticks recorded after each speed run's hit");
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
  // Every dye, red last so each repaint changes the color it finds.
  for (const name of [...PALETTE.slice(1), PALETTE[0]]) {
    driver.setItem(new ItemStack(`minecraft:${name}_dye`, 3), 0, true);
    driver.isSneaking = true;
    await wait(4);
    driver.interactWithEntity(truck);
    await wait(6);
    driver.isSneaking = false;
    const color = truck.getProperty("blake:color");
    const left = driver.getComponent("minecraft:inventory").container.getItem(0)?.amount;
    if (color !== PALETTE.indexOf(name)) throw new Error(`Sneak-Dye Repainting with ${name} dye gave color ${color}`);
    if (left !== 3) throw new Error(`Sneak-Dye Repainting consumed ${name} dye: ${left} left`);
    if (riders(truck).length) throw new Error(`Sneak-interact with ${name} dye mounted the truck`);
  }
  return ["sneak-interact with each of the 16 dyes repaints the truck to that dye's color",
    "no dye consumed and nobody mounted"];
}

// Spawn sources: a bare summon is red, each blake:spawn_<color> event gives exactly its color,
// the crafted Vehicle Item deploys red, and the Creative spawn egg randomizes across all 16.
async function spawn_sources({ dimension, origin, driver, run }) {
  const checks = [];
  const spot = at(origin, 0, 6);
  const trucksNear = () => dimension.getEntities({ type: run.entity_id, location: spot, maxDistance: 8 });
  const spawnedColor = async (spawn, label) => {
    trucksNear().forEach(truck => truck.remove());
    await spawn();
    await wait(2);
    const found = trucksNear();
    if (found.length !== 1) throw new Error(`${label} spawned ${found.length} trucks`);
    const color = found[0].getProperty("blake:color");
    found[0].remove();
    return color;
  };
  const summon = event => async () => dimension.runCommand(
    `summon ${run.entity_id} ${spot.x} ${spot.y} ${spot.z} 0 0${event ? " " + event : ""}`);

  const bare = await spawnedColor(summon(), "bare summon");
  if (bare !== 0) throw new Error("Bare summon is not red: color " + bare);
  checks.push("bare summon spawns red");
  for (const [index, name] of PALETTE.entries()) {
    const color = await spawnedColor(summon(`blake:spawn_${name}`), `blake:spawn_${name}`);
    if (color !== index) throw new Error(`blake:spawn_${name} spawned color ${color}, expected ${index}`);
  }
  checks.push("each of the 16 blake:spawn_<color> events spawns exactly its color");

  // Items are placed through the Simulated Driver's real item use on the ground block.
  const ground = { x: Math.floor(spot.x), y: GROUND_Y - 1, z: Math.floor(spot.z) };
  driver.teleport(at(origin, -3, 6));
  await wait(4);
  // A Simulated Driver's item uses are rate-limited (a use rejected right after the last one
  // registered within 8 ticks of retrying in Scenario Runs), so click until it registers.
  let maxUseWait = 0;
  const place = itemId => async () => {
    for (let tick = 0; tick < 40; tick++) {
      if (driver.useItemOnBlock(new ItemStack(itemId), ground, Direction.Up)) {
        maxUseWait = Math.max(maxUseWait, tick);
        return;
      }
      await wait(1);
    }
    throw new Error(`${itemId} use never registered in 40 ticks`);
  };
  const crafted = [];
  for (let i = 0; i < 8; i++) crafted.push(await spawnedColor(place("blake:monster_truck_vehicle"), "Vehicle Item"));
  if (crafted.some(color => color !== 0)) throw new Error("Vehicle Item did not deploy red: " + crafted.join(","));
  checks.push("Survival: 8 placements of the crafted Vehicle Item all deploy red");

  // 200 placements: the chance a uniform 16-way pick misses any color is about 4e-5.
  const counts = new Array(PALETTE.length).fill(0);
  driver.setGameMode(GameMode.Creative);
  try {
    for (let i = 0; i < 200; i++) {
      const color = await spawnedColor(place("blake:monster_truck_spawn_egg"), "spawn egg");
      if (!(color >= 0 && color < PALETTE.length)) throw new Error("Spawn egg gave invalid color " + color);
      counts[color]++;
    }
  } finally {
    driver.setGameMode(GameMode.Survival);
  }
  const missing = PALETTE.filter((_, index) => counts[index] === 0);
  if (missing.length) throw new Error(`Spawn egg never produced ${missing.join(", ")} in 200 placements: ${counts.join(",")}`);
  checks.push(`Creative: 200 spawn egg placements produced all 16 colors (counts ${counts.join(",")}); item use waited up to ${maxUseWait} ticks`);
  return checks;
}

// The retrieval bench: a truck spawned, destroyed by kill(truck), and the items it dropped counted.
function retrievalBench({ dimension, origin, run }) {
  const location = at(origin, 0, 6);
  const clear = () => dimension.getEntities({ type: "minecraft:item", location, maxDistance: 6 }).forEach(item => item.remove());
  // A killed entity can stay valid through its death animation.
  const dead = truck => !truck.isValid || health(truck) <= 0;
  // Items are counted as they spawn, so drops that land in fire (lightning ignites the ground)
  // still count. kill(truck) destroys the truck and resolves once it is gone.
  const destroy = async kill => {
    clear();
    const totals = new Map();
    const spawned = world.afterEvents.entitySpawn.subscribe(({ entity }) => {
      if (entity.typeId !== "minecraft:item" || horizontal(entity.location, location) > 6) return;
      const stack = entity.getComponent("minecraft:item")?.itemStack;
      if (stack) totals.set(stack.typeId, (totals.get(stack.typeId) || 0) + stack.amount);
    });
    try {
      const truck = spawnTruck(dimension, run, location);
      await wait(5);
      await kill(truck);
      if (!dead(truck)) throw new Error("truck survived: health " + health(truck));
      await wait(10);
    } finally {
      world.afterEvents.entitySpawn.unsubscribe(spawned);
    }
    clear();
    return totals;
  };
  return { dead, destroy };
}

async function retrieval({ dimension, origin, driver, run }) {
  const { dead, destroy } = retrievalBench({ dimension, origin, run });
  const applied = cause => async truck => {
    truck.applyDamage(5000, { cause });
    await wait(2);
  };
  const scrapOnly = (drops, label) => {
    if ((drops.get("minecraft:iron_ingot") || 0) < 1 || drops.has("blake:monster_truck_vehicle")) {
      throw new Error(`${label} must drop Scrap only: ${JSON.stringify([...drops])}`);
    }
  };

  // A real swing from a Survival player, with the truck worn down first: the blow that would
  // kill it returns the Vehicle Item. retrieval_full_health swings from full health (opt-in: 2 minutes).
  let swings = 0;
  const retrieved = await destroy(async truck => {
    truck.getComponent("minecraft:health").setCurrentValue(1);
    for (let tick = 0; tick < 100 && !dead(truck); tick++) {
      if (driver.attackEntity(truck)) swings++;
      await wait(1);
    }
  });
  if (retrieved.get("blake:monster_truck_vehicle") !== 1 || retrieved.has("minecraft:iron_ingot")) {
    throw new Error("Player-fatal retrieval must return exactly one Vehicle Item: " + JSON.stringify([...retrieved]));
  }
  const checks = [`a player's punches (${swings} swings at a worn-down truck) return exactly one Vehicle Item and no Scrap`];

  for (const cause of [EntityDamageCause.entityExplosion, EntityDamageCause.lava, EntityDamageCause.fire]) {
    scrapOnly(await destroy(applied(cause)), `${cause} destruction`);
  }
  checks.push("explosion, lava, and fire destruction drop Scrap only");

  // Mob combat: a zombie's fatal blow.
  const zombie = dimension.spawnEntity("minecraft:zombie", at(origin, 6, 6));
  try {
    scrapOnly(await destroy(async truck => {
      truck.applyDamage(5000, { cause: EntityDamageCause.entityAttack, damagingEntity: zombie });
      await wait(2);
    }), "a zombie's fatal blow");
  } finally {
    if (zombie.isValid) zombie.remove();
  }
  checks.push("a zombie's fatal blow drops Scrap only");

  // Lightning: a real bolt on a worn-down truck; the killing blow must be the lightning itself.
  let killedBy;
  const died = world.afterEvents.entityDie.subscribe(event => {
    if (event.deadEntity.typeId === run.entity_id) killedBy = event.damageSource.cause;
  });
  try {
    scrapOnly(await destroy(async truck => {
      truck.getComponent("minecraft:health").setCurrentValue(1);
      dimension.spawnEntity("minecraft:lightning_bolt", truck.location);
      for (let tick = 0; tick < 40 && !dead(truck); tick++) await wait(1);
    }), "a lightning kill");
  } finally {
    world.afterEvents.entityDie.unsubscribe(died);
  }
  if (killedBy !== EntityDamageCause.lightning) throw new Error("Lightning test truck was killed by " + killedBy);
  checks.push("a lightning strike's fatal blow drops Scrap only");
  return checks;
}

async function retrieval_full_health({ dimension, origin, driver, run }) {
  const { dead, destroy } = retrievalBench({ dimension, origin, run });
  // Real swings from a Survival player take a fresh truck from full health to the fatal blow,
  // which returns the Vehicle Item. Measured (run 2849f48e): one hit lands every 10 ticks (the
  // damage immunity window; attackEntity returns false in between). A fist deals 1 (about 500 s
  // from full); after the 0.25 entity_attack multiplier a netherite sword deals 2.25 and a
  // Sharpness V netherite sword 3.75: 266 swings, 2666 ticks (about 133 s, run 11fa266d). The
  // Sharpness V sword keeps the Scenario Run bounded. Over that long, slimes and other hostile
  // mobs spawned, knocked the driver about (some swings landed as 5.625 critical hits) and killed
  // them, dropping the sword (runs 12e6c450, f74d9c78), so the swings run on Peaceful.
  const inventory = driver.getComponent("minecraft:inventory").container;
  const sword = new ItemStack("minecraft:netherite_sword", 1);
  sword.getComponent("minecraft:enchantable").addEnchantment({ type: new EnchantmentType("sharpness"), level: 5 });
  inventory.setItem(driver.selectedSlotIndex, sword);
  let swings = 0;
  let startHealth;
  const startTick = system.currentTick;
  let retrieved;
  const difficulty = world.getDifficulty();
  world.setDifficulty(Difficulty.Peaceful);
  try {
    retrieved = await destroy(async truck => {
      startHealth = health(truck);
      for (let tick = 0; tick < 3200 && !dead(truck); tick++) {
        if (driver.attackEntity(truck)) swings++;
        await wait(1);
      }
    });
  } finally {
    inventory.setItem(driver.selectedSlotIndex, undefined);
    world.setDifficulty(difficulty);
  }
  if (startHealth !== TRUCK_MAX_HEALTH) throw new Error(`Retrieval truck started at ${startHealth} health, not full`);
  if (retrieved.get("blake:monster_truck_vehicle") !== 1 || retrieved.has("minecraft:iron_ingot")) {
    throw new Error("Player-fatal retrieval must return exactly one Vehicle Item: " + JSON.stringify([...retrieved]));
  }
  return [`a player's swings (Sharpness V netherite sword, ${swings} swings over ` +
    `${system.currentTick - startTick} ticks from ${startHealth} health) ` +
    "return exactly one Vehicle Item and no Scrap"];
}

// Two players share the truck and swap seats: both leave by Sneak, the passenger takes the Driver
// Seat and the first driver the Passenger Seat. Only whoever holds seat 0 drives.
async function seat_swap({ dimension, origin, driver, run, spawnPlayer }) {
  const checks = [];
  const truck = spawnTruck(dimension, run, at(origin, 0, 2));
  await wait(10);
  await board(driver, truck, 0);
  const second = spawnPlayer("SimulatedPassenger");
  await wait(10);
  await board(second, truck, 1);
  checks.push(`${driver.name} took the Driver Seat and ${second.name} the Passenger Seat`);

  const exits = [];
  for (const player of [driver, second]) exits.push(await sneakOut(truck, player));
  for (const player of [driver, second]) player.isSneaking = false;
  await wait(5);
  if (riders(truck).length) throw new Error("Truck still had riders after both left: " + riders(truck).map(r => r?.name).join(","));
  checks.push("both left by Sneak: " + exits.join("; "));

  await board(second, truck, 0);
  await board(driver, truck, 1);
  for (const [player, seat] of [[second, 0], [driver, 1]]) {
    if (player.getComponent("minecraft:riding")?.entityRidingOn?.id !== truck.id) throw new Error(`${player.name} in seat ${seat} is not riding the truck`);
  }
  checks.push(`swapped: ${second.name} in the Driver Seat, ${driver.name} in the Passenger Seat, both riding the truck`);

  // The new passenger's full forward input must not drive; the new driver's must.
  const parked = truck.location;
  const { movement } = driverInput;
  driverInput.movement = player => (player.id === driver.id ? { x: 0, y: 1 } : movement(player));
  try {
    await wait(30);
  } finally {
    driverInput.movement = movement;
  }
  const passengerMoved = horizontal(truck.location, parked);
  if (passengerMoved > 0.5) throw new Error(`New passenger's input moved the truck ${passengerMoved.toFixed(2)} blocks`);
  const before = truck.location;
  await drive(second, 20);
  const driverMoved = horizontal(truck.location, before);
  if (driverMoved < 5) throw new Error(`New driver's input moved the truck only ${driverMoved.toFixed(2)} blocks`);
  checks.push(`after the swap the passenger's input moved the truck ${passengerMoved.toFixed(2)} blocks and ` +
    `the new driver's ${driverMoved.toFixed(1)} blocks in 20 ticks`);
  return checks;
}

async function incline_pitch({ dimension, origin, driver, run }) {
  const checks = [];
  for (const [rise, run_] of [[1, 2], [1, 3], [1, 1]]) {
    park(driver, origin);
    resetArena(dimension, origin);
    // At least 20 blocks of run per flight, so pitch settles past its smoothing ramp.
    const steps = Math.max(10, Math.ceil(20 / run_));
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
    await drive(driver, 260, {
      forward: 0.5,
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
    const { low, high } = pitchBand(rise, run_);
    const mean = values => values.reduce((a, b) => a + b, 0) / Math.max(values.length, 1);
    const label = `${rise}:${run_} (expected ${low.toFixed(1)}° to ${high.toFixed(1)}°)`;
    if (!up.length || !down.length || truck.location.z - origin.z < downEnd + 1) {
      throw new Error(`${label}: truck did not traverse the ramp to flat ground (z=${(truck.location.z - origin.z).toFixed(1)})`);
    }
    if (mean(up) < low || mean(up) > high) throw new Error(`${label}: uphill mean pitch ${mean(up).toFixed(1)}° ${JSON.stringify(up)}`);
    if (-mean(down) < low || -mean(down) > high) throw new Error(`${label}: downhill mean pitch ${mean(down).toFixed(1)}° ${JSON.stringify(down)}`);
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
  smoke, seats, auto_step, steering, handbrake, crush_stomp, shock_absorption,
  flotation_water, flotation_lava, trample, demolition, foliage_shearing,
  dye_repaint, retrieval, retrieval_full_health, incline_pitch, spawn_sources, two_seat_drop,
  liquid_start_water, liquid_start_lava, shoreline_wall, shoreline_step, seat_swap,
};
