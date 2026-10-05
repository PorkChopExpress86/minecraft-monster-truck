// One Monster Truck tick: driving, steering and pitch, liquids, then the drop lifecycle
// (landing.js), Tire Trample and heavy collisions (contact.js), and demolition (demolition.js).
// main.js calls tickTruck for every truck each tick with the real Script API Entity and
// Dimension; tests pass fakes implementing the subset typed below. This module must not import
// @minecraft/server, so node can load it.
import { demolishAhead } from "./demolition.js";
import {
  calculateDynamicPitch,
  sampleGroundHeight
} from "./kinematics.js";
import {
  classifyShorelineColumn,
  isLiquidBlock,
  LIQUID_DRAG_RETENTION,
  SHORELINE_LIFT,
  shorelineLiftVelocity
} from "./amphibious.js";
import { createDrivingState, groundRetention, headingVector, stepDriving } from "./driving.js";
import { AXLE_OFFSET } from "./geometry.js";
import { MOLTEN_TIRE_TICKS, stepContact } from "./contact.js";
import { createLandingState, releaseLanding, stepLanding } from "./landing.js";

/**
 * The Script API subset tickTruck uses. Production passes @minecraft/server objects.
 * @typedef {{ x: number, y: number, z: number }} Vector3
 * @typedef {{ x: number, y: number }} Vector2
 * An EntityDamageCause member's string value (the enum itself lives in @minecraft/server).
 * @typedef {`${import("@minecraft/server").EntityDamageCause}`} DamageCause
 * @typedef {{ cause?: DamageCause, damagingEntity?: TruckEntity }} DamageOptions
 * @typedef {{
 *   id: string,
 *   typeId: string,
 *   isValid: boolean,
 *   location: Vector3,
 *   isSneaking?: boolean,
 *   applyImpulse(vector: Vector3): void,
 *   applyDamage(amount: number, options?: DamageOptions): boolean,
 *   setOnFire?(seconds: number, useEffects?: boolean): boolean,
 *   extinguishFire?(useEffects?: boolean): boolean,
 *   teleport?(location: Vector3, options?: { dimension?: any }): void,
 *   getComponent?(componentId: string): any,
 * }} WorldEntity
 * @typedef {{
 *   getRiders(): WorldEntity[],
 *   addRider(rider: WorldEntity): boolean,
 * }} Rideable
 * The truck's only component read is its rideable, typed so tsc checks the real
 * EntityRideableComponent against Rideable.
 * @typedef {Omit<WorldEntity, "getComponent"> & {
 *   isOnGround: boolean,
 *   getVelocity(): Vector3,
 *   clearVelocity(): void,
 *   getRotation(): Vector2,
 *   setRotation(rotation: Vector2): void,
 *   setProperty(identifier: string, value: boolean | number | string): void,
 *   getComponent(componentId: "minecraft:rideable"): Rideable | undefined,
 * }} TruckEntity
 * @typedef {{ typeId: string, isAir: boolean, setType(blockType: string): void }} WorldBlock
 * @typedef {{
 *   getBlock(location: Vector3): WorldBlock | undefined,
 *   getEntities(options?: { type?: string, location?: Vector3, maxDistance?: number }): WorldEntity[],
 *   spawnParticle(effectName: string, location: Vector3): void,
 *   playSound(soundId: string, location: Vector3, soundOptions?: { volume?: number, pitch?: number }): void,
 *   runCommand(commandString: string): unknown,
 * }} WorldDimension
 * @typedef {{
 *   movement(driver: WorldEntity): Vector2,
 *   handbrake(driver: WorldEntity): boolean,
 * }} DriverInput
 * What a tick needs from outside the truck and its dimension.
 * driverInput: the driver-input seam (main.js driverInput, ADR-0016).
 * getEntity: world-wide entity lookup by id (world.getEntity).
 * protectedRiders: rider id -> truck id whose fall protects them (read by the entityHurt handler).
 * @typedef {{
 *   driverInput: DriverInput,
 *   getEntity(id: string): WorldEntity | undefined,
 *   protectedRiders: Map<string, string>,
 * }} TickInput
 * landing: landing.js's slice (the drop lifecycle).
 * hitCooldowns: entity id -> tick this truck last trampled it (contact.js).
 * jumpHeldAt: rider id -> last tick that rider held Jump (Space) while seated.
 * @typedef {Record<string, any> & {
 *   landing: import("./landing.js").LandingState,
 *   hitCooldowns: Map<string, number>,
 *   jumpHeldAt: Map<string, number>,
 * }} TruckState
 */

// Minecraft dismounts a rider who presses Space (Jump, the add-on's handbrake). An exit within this many
// ticks of the rider holding Jump is that dismount, not a Sneak exit (landing.js). Measured in the real
// client: Jump reads pressed the tick before such an exit and for 4+ ticks after it (Client Input Run).
const SPACE_EXIT_GRACE_TICKS = 3;
// InputPermissionCategory.Jump (@minecraft/server), spelled out so node can load this module. main.js turns
// it off for seated players (#40), and then Space cannot dismount them: any exit is Sneak, Space held or not.
const JUMP_PERMISSION = 6;

// Horizontal velocity the engine keeps per tick while airborne; measured in
// docs/agents/bedrock-physics.md (Air row) — read it before retuning.
const AIR_DRAG_RETENTION = 0.91;

/** @returns {TruckState} */
export function createTruckState() {
  return { landing: createLandingState(), hitCooldowns: new Map(), jumpHeldAt: new Map() };
}

/**
 * The truck is no longer in the world: undo what its state holds outside itself (its riders'
 * fall protection). The caller then drops the state, and its hit cooldowns with it.
 * @param {string} truckId
 * @param {TruckState} state
 * @param {TickInput} input
 */
export function releaseTruck(truckId, state, input) {
  releaseLanding(state.landing, truckId, input.protectedRiders);
}

/**
 * Advance one truck by one tick. Mutates state; acts on the truck and dimension.
 * @param {TruckEntity} truck
 * @param {WorldDimension} dimension
 * @param {TruckState} state
 * @param {TickInput} input
 * @param {number} tick
 */
export function tickTruck(truck, dimension, state, input, tick) {
  const { driverInput, getEntity, protectedRiders } = input;
  const loc = truck.location;
  if (state.prevX === undefined) {
    // First tick for this truck: no motion yet.
    state.prevX = loc.x;
    state.prevY = loc.y;
    state.prevZ = loc.z;
  }

  const dx = loc.x - state.prevX;
  const dy = loc.y - state.prevY;
  const dz = loc.z - state.prevZ;

  // Update state for next tick
  state.prevX = loc.x;
  state.prevY = loc.y;
  state.prevZ = loc.z;

  const horizontalDist = Math.hypot(dx, dz);
  let velSpeed = 0;
  let vel;
  try {
    vel = truck.getVelocity ? truck.getVelocity() : undefined;
    if (vel) {
      velSpeed = Math.hypot(vel.x, vel.z);
    }
  } catch {}

  const effectiveSpeed = Math.max(horizontalDist, velSpeed);
  const tickNumber = tick;

  // Compute heading vector
  let dirX = 0;
  let dirZ = 0;
  if (horizontalDist > 0.01) {
    dirX = dx / horizontalDist;
    dirZ = dz / horizontalDist;
  } else if (vel && velSpeed > 0.01) {
    dirX = vel.x / velSpeed;
    dirZ = vel.z / velSpeed;
  } else {
    try {
      const rot = truck.getRotation();
      const rad = (rot.y + 90) * (Math.PI / 180);
      dirX = Math.cos(rad);
      dirZ = Math.sin(rad);
    } catch {
      dirX = 1;
      dirZ = 0;
    }
  }

  // Perpendicular vector for lateral width
  const perpX = -dirZ;
  const perpZ = dirX;

  // Rider monitoring, thermal shielding, and safe dismount
  const rideable = truck.getComponent ? truck.getComponent("minecraft:rideable") : undefined;
  // A seat can hold a rider this script runtime cannot see (undefined): it stays a seat, so the rider
  // after it is not promoted to driver, but only seen riders are tracked.
  const currentRiders = rideable && rideable.getRiders ? rideable.getRiders() : [];
  const prevRiders = state.riders || [];
  state.riders = currentRiders.filter((r) => r != null).map((r) => r.id);
  // Jump is read for every rider through the driver-input seam's handbrake (the Jump button).
  for (const rider of currentRiders) {
    try {
      if (driverInput.handbrake(rider)) state.jumpHeldAt.set(rider.id, tickNumber);
    } catch {}
  }
  for (const [riderId, heldAt] of state.jumpHeldAt) {
    if (tickNumber - heldAt > SPACE_EXIT_GRACE_TICKS) state.jumpHeldAt.delete(riderId);
  }
  const jumpedRecently = (player) => {
    try {
      if (!player.inputPermissions.isPermissionCategoryEnabled(JUMP_PERMISSION)) return false;
    } catch {}
    try {
      if (driverInput.handbrake(player)) return true;
    } catch {}
    return state.jumpHeldAt.has(player.id);
  };

  // Check if truck is in lava or water
  let inLava = false;
  let inWater = false;
  try {
    const block = dimension.getBlock(loc);
    if (block) {
      if (block.typeId === "minecraft:lava" || block.typeId === "minecraft:flowing_lava") inLava = true;
      if (block.typeId === "minecraft:water" || block.typeId === "minecraft:flowing_water") inWater = true;
    }
  } catch {}

  // Thermal shielding in lava: extinguish fire ticks on riders
  if (inLava) {
    state.moltenUntil = tickNumber + MOLTEN_TIRE_TICKS;
    for (const rider of currentRiders) {
      try {
        if (rider.extinguishFire) rider.extinguishFire(false);
      } catch {}
    }
  }

  const driver = currentRiders.length > 0 ? currentRiders[0] : undefined;

  // Script-driven driving (ADR-0017): W/S throttle, A/D steer the wheels, Jump held is
  // the handbrake. The truck's yaw is owned here; the driver's mouse only moves the camera.
  /** @type {{ forward?: number, strafe?: number, handbrake?: boolean }} */
  let driverControls = {};
  if (driver) {
    try {
      const movement = driverInput.movement(driver);
      driverControls = { forward: movement.y, strafe: movement.x };
    } catch {}
    try {
      driverControls.handbrake = driverInput.handbrake(driver);
    } catch {}
  }
  if (!state.driving) {
    let spawnYaw = 0;
    try { spawnYaw = truck.getRotation().y; } catch {}
    state.driving = createDrivingState(spawnYaw);
  }
  const inLiquid = inWater || inLava;
  // A Shoreline Step-Up lifts the truck clear of the liquid; keep driving it forward over
  // the bank's edge while it rises and for 8 ticks after.
  const steppingAshore = state.shoreLift !== undefined ||
    (state.lastShorelineStep !== undefined && tickNumber - state.lastShorelineStep < 8);
  const onGround = Boolean(truck.isOnGround);
  const wheelsDown = inLiquid || onGround || steppingAshore;
  const lastMotion = headingVector(state.driving.yaw + state.driving.slip);
  const wasMoving = state.driving.speed !== 0;
  const drive = stepDriving(state.driving, driverControls, {
    grounded: wheelsDown,
    // Afloat, a bank is climbed by Shoreline Step-Up, so keep pushing rather than stopping.
    measuredSpeed: wasMoving && !inLiquid ? dx * lastMotion.x + dz * lastMotion.z : undefined
  });
  state.driving = drive.state;
  if (wheelsDown && (wasMoving || drive.state.speed !== 0 || driverControls.handbrake)) {
    // Replace the engine's horizontal velocity with the driven one. The engine applies ground
    // friction or liquid drag before moving the truck, so ask for what survives it.
    let retention = inLava ? LIQUID_DRAG_RETENTION.lava : inWater ? LIQUID_DRAG_RETENTION.water : undefined;
    if (retention === undefined && !onGround) {
      retention = AIR_DRAG_RETENTION;
    } else if (retention === undefined) {
      let ground;
      try { ground = dimension.getBlock({ x: loc.x, y: loc.y - 0.5, z: loc.z })?.typeId; } catch {}
      retention = groundRetention(ground);
    }
    const current = vel || { x: 0, z: 0 };
    try {
      truck.applyImpulse({
        x: drive.velocity.x / retention - current.x,
        y: 0,
        z: drive.velocity.z / retention - current.z
      });
    } catch {}
  }
  try {
    truck.setRotation({ x: 0, y: drive.state.yaw });
  } catch {}

  // Coordinated Four-Wheel Steering: the front wheels show the A/D steering angle.
  state.steerAngle = Math.round(drive.state.steer);
  try {
    truck.setProperty("blake:steer_angle", state.steerAngle);
  } catch {}

  const verticalVelocity = vel ? vel.y : dy;

  // Shoreline Step-Up: driving forward against a bank flush with the liquid surface or up to
  // 2 blocks above it lifts the truck out. Propulsion on liquids is the driving above.
  const isNonAirNonLiquid = (b) => b && !b.isAir && b.typeId !== "minecraft:air" && !isLiquidBlock(b.typeId);
  const forwardHeld = (driverControls.forward ?? 0) > 0.05;
  // A lift that gave up stays off until W is pressed again or the truck leaves that bank.
  if (!forwardHeld) delete state.shoreLiftGaveUp;
  if (!state.shoreLift && inLiquid && driver && forwardHeld) {
    // Count the bank from the liquid surface: the top liquid block in the truck's column, which
    // is above the truck's own block when it floats deeper.
    let baseY = Math.floor(loc.y);
    try {
      for (let i = 0; i < 3 && isLiquidBlock(dimension.getBlock({ x: loc.x, y: baseY + 1, z: loc.z })?.typeId); i++) baseY++;
    } catch {}
    const intentDir = headingVector(drive.state.yaw);
    const intentPerp = { x: -intentDir.z, z: intentDir.x };
    let bankFound = null;

    try {
      for (const lat of [0, -0.8, 0.8]) {
        const checkX = Math.floor(loc.x + intentDir.x * 1.5 + intentPerp.x * lat);
        const checkZ = Math.floor(loc.z + intentDir.z * 1.5 + intentPerp.z * lat);
        const column = [0, 1, 2, 3].map((h) => isNonAirNonLiquid(dimension.getBlock({ x: checkX, y: baseY + h, z: checkZ })));
        const res = classifyShorelineColumn(column);
        if (res.isShoreline) {
          bankFound = res;
          break;
        }
      }

      if (!bankFound) {
        delete state.shoreLiftGaveUp;
      } else if (!state.shoreLiftGaveUp) {
        state.shoreLift = { topY: baseY + bankFound.stepHeight, startTick: tickNumber };
      }
    } catch {}
  }
  // The lift sets the vertical velocity every tick until the truck is over the bank (SHORELINE_LIFT).
  if (state.shoreLift) {
    const lift = state.shoreLift;
    let overBank = false;
    if (loc.y >= lift.topY) {
      try {
        overBank = Boolean(isNonAirNonLiquid(dimension.getBlock({ x: loc.x, y: lift.topY - 0.5, z: loc.z })));
      } catch {}
    }
    const gaveUp = tickNumber - lift.startTick >= SHORELINE_LIFT.maxTicks;
    if (overBank || !driver || !forwardHeld || gaveUp) {
      delete state.shoreLift;
      if (gaveUp && !overBank) state.shoreLiftGaveUp = true;
      // However the lift ends, drop its remaining climb so the truck settles instead of hopping.
      if (vel && vel.y > 0) {
        try {
          truck.applyImpulse({ x: 0, y: -vel.y, z: 0 });
        } catch {}
      }
    } else {
      state.lastShorelineStep = tickNumber;
      try {
        truck.applyImpulse({ x: 0, y: shorelineLiftVelocity(loc.y, lift.topY) - (vel ? vel.y : 0), z: 0 });
      } catch {}
    }
  }

  // Dual rooster-tail liquid wake particles and churning audio while moving across water or lava
  if ((inWater || inLava) && effectiveSpeed > 0.08) {
    try {
      const leftX = loc.x - dirX * 1.6 + perpX * 0.85;
      const leftZ = loc.z - dirZ * 1.6 + perpZ * 0.85;
      const rightX = loc.x - dirX * 1.6 - perpX * 0.85;
      const rightZ = loc.z - dirZ * 1.6 - perpZ * 0.85;
      const wakeY = loc.y + 0.35;

      if (inWater) {
        dimension.spawnParticle("minecraft:water_splash_particle", { x: leftX, y: wakeY, z: leftZ });
        dimension.spawnParticle("minecraft:water_splash_particle", { x: rightX, y: wakeY, z: rightZ });
        if (tickNumber % 8 === 0) {
          dimension.playSound("random.splash", loc, { volume: 0.8, pitch: 0.75 });
        }
      } else if (inLava) {
        dimension.spawnParticle("minecraft:lava_particle", { x: leftX, y: wakeY, z: leftZ });
        dimension.spawnParticle("minecraft:lava_particle", { x: rightX, y: wakeY, z: rightZ });
        if (tickNumber % 10 === 0) {
          dimension.playSound("random.fizz", loc, { volume: 0.9, pitch: 0.65 });
        }
      }
    } catch {}
  }

  // The drop lifecycle: rider retention, free fall, Pneumatic Shock Absorption, Crush Stomp.
  stepLanding(truck, dimension, state.landing, {
    location: loc,
    dy,
    verticalVelocity,
    heading: { x: dirX, z: dirZ },
    rideable,
    riderIds: state.riders,
    prevRiderIds: prevRiders,
    inLiquid: inLava || inWater,
    inLava,
    tick: tickNumber,
    getEntity,
    protectedRiders,
    jumpedRecently
  });

  // Dynamic Incline Pitch, after the drop lifecycle so this tick's takeoff or landing picks the branch.
  const truckRot = truck.getRotation ? truck.getRotation() : { y: 0 };
  const headRad = (truckRot.y + 90) * (Math.PI / 180);
  const headX = Math.cos(headRad);
  const headZ = Math.sin(headRad);

  const frontX = loc.x + headX * AXLE_OFFSET;
  const frontZ = loc.z + headZ * AXLE_OFFSET;
  const rearX = loc.x - headX * AXLE_OFFSET;
  const rearZ = loc.z - headZ * AXLE_OFFSET;

  const frontHeight = sampleGroundHeight(dimension, frontX, loc.y, frontZ);
  const rearHeight = sampleGroundHeight(dimension, rearX, loc.y, rearZ);

  state.pitchAngle = calculateDynamicPitch({
    frontHeight,
    rearHeight,
    currentPitch: state.pitchAngle || 0,
    isAirborne: Boolean(state.landing.isFalling),
    inLiquid: inWater || inLava,
    verticalVelocity,
    horizontalSpeed: effectiveSpeed
  });
  try {
    truck.setProperty("blake:pitch_angle", state.pitchAngle);
  } catch {}

  // Tire Trample, Molten Tire Trample, and heavy collisions with what the truck touches.
  stepContact(truck, dimension, {
    location: loc,
    heading: { x: dirX, z: dirZ },
    speed: effectiveSpeed,
    moltenUntil: state.moltenUntil,
    hitCooldowns: state.hitCooldowns,
    tick: tickNumber
  });

  // Foliage Shearing at any speed with a driver; Wood Demolition needs momentum.
  demolishAhead(dimension, {
    location: loc,
    heading: { x: dirX, z: dirZ },
    speed: effectiveSpeed,
    hasDriver: Boolean(driver)
  });
}
