// Script-driven driving (ADR-0017): W/S throttle, brake, and reverse; A/D steer the front
// wheels; holding Jump locks the rear wheels for a Handbrake Drift. The mouse only moves the
// camera. Speeds are blocks/tick, angles degrees, yaw in Minecraft convention (0 faces +Z).

import { MAX_STEER_DEGREES } from "./kinematics.js";

export const DRIVING = {
  topSpeed: 1.1,               // ~22 blocks/s: the overland speed players already liked
  reverseTopSpeed: 0.37,       // a third of top speed
  acceleration: 0.037,         // ~1.5 s from rest to top speed
  coastDeceleration: 0.0275,   // ~2 s to coast to a stop
  brakeDeceleration: 0.08,     // S while rolling forward (or W while reversing)
  handbrakeDeceleration: 0.05, // locked rear wheels: ~1.1 s from top speed
  wheelbase: 3.0,              // blocks between axles; sets the turning radius
  steerRate: 4,                // degrees per tick the front wheels turn toward the A/D target
  highSpeedSteerShare: 0.4,    // share of full lock that still turns the truck at top speed
  handbrakeYawBoost: 2.0,      // the rear steps out: the truck turns twice as fast
  handbrakeGrip: 0.04,         // share of the slide angle recovered per tick while sliding
  gripRecovery: 0.3,           // share recovered per tick after release (~0.5 s)
  slideEndDegrees: 2,          // below this the tires have full grip again
  maxSlideDegrees: 90,
  blockedTolerance: 0.15,      // speed lost to a wall beyond this is taken from the measured motion
};

// Share of horizontal velocity the engine keeps after ground friction, which it applies before
// moving the truck: 0.91 x block slipperiness (0.6 for most blocks), scaled by the entity's
// minecraft:friction_modifier. Driving divides its velocity by this so the truck covers its
// speed on any surface.
const SLIPPERINESS = {
  "minecraft:ice": 0.98,
  "minecraft:packed_ice": 0.98,
  "minecraft:frosted_ice": 0.98,
  "minecraft:blue_ice": 0.989,
  "minecraft:slime": 0.8,
};

export const FRICTION_MODIFIER = 1.15; // monster_truck.entity.json minecraft:friction_modifier

export function groundRetention(blockTypeId) {
  return Math.min(1, 0.91 * (SLIPPERINESS[blockTypeId] ?? 0.6) * FRICTION_MODIFIER);
}

// Movement vector x is +1 for A (left) and -1 for D (right).
export const LEFT_INPUT_SIGN = 1;

const RAD = Math.PI / 180;

export function headingVector(yaw) {
  return { x: -Math.sin(yaw * RAD), z: Math.cos(yaw * RAD) };
}

// Step toward target; snaps to it when within float noise so values settle exactly (and never -0).
function approach(value, target, step) {
  const next = value < target ? Math.min(target, value + step) : Math.max(target, value - step);
  return Math.abs(next - target) < 1e-9 ? target + 0 : next;
}

function wrapDegrees(angle) {
  return ((angle + 540) % 360) - 180;
}

export function createDrivingState(yaw = 0) {
  return { speed: 0, yaw, steer: 0, slip: 0, sliding: false };
}

/**
 * Advance one tick. input: { forward, strafe } from the movement vector plus handbrake.
 * grounded: wheels on ground or floating (no control while airborne).
 * measuredSpeed: signed distance actually covered along the motion direction last tick.
 * Returns the next state plus the planar velocity the truck should move with this tick.
 * @param {{ speed: number, yaw: number, steer: number, slip: number, sliding: boolean }} state
 * @param {{ forward?: number, strafe?: number, handbrake?: boolean }} [input]
 * @param {{ grounded?: boolean, measuredSpeed?: number, config?: typeof DRIVING }} [options]
 */
export function stepDriving(state, { forward = 0, strafe = 0, handbrake = false } = {}, {
  grounded = true,
  measuredSpeed,
  config = DRIVING,
} = {}) {
  let { speed, yaw, steer, slip, sliding } = state;

  // Front wheels turn toward the A/D target and spring back to center when released.
  const steerTarget = -Math.sign(strafe * LEFT_INPUT_SIGN) * Math.min(1, Math.abs(strafe)) * MAX_STEER_DEGREES;
  steer = approach(steer, steerTarget, config.steerRate);

  if (grounded) {
    // A wall or heavy mob stopped the truck: continue from the motion actually achieved.
    if (measuredSpeed !== undefined && Math.abs(measuredSpeed) + config.blockedTolerance < Math.abs(speed)) {
      speed = measuredSpeed;
    }

    if (handbrake) {
      speed = approach(speed, 0, config.handbrakeDeceleration);
    } else if (forward > 0.05) {
      speed = speed < 0
        ? approach(speed, 0, config.brakeDeceleration)
        : approach(speed, config.topSpeed * Math.min(1, forward), config.acceleration);
    } else if (forward < -0.05) {
      speed = speed > 0
        ? approach(speed, 0, config.brakeDeceleration)
        : approach(speed, -config.reverseTopSpeed * Math.min(1, -forward), config.acceleration);
    } else {
      speed = approach(speed, 0, config.coastDeceleration);
    }

    // Bicycle model: the truck turns only while rolling, in a wider arc at speed. Reversing
    // with the wheels turned swings the nose the other way, as in a real car.
    const speedShare = Math.min(1, Math.abs(speed) / config.topSpeed);
    const effectiveSteer = steer * (1 - (1 - config.highSpeedSteerShare) * speedShare);
    let yawRate = (speed / config.wheelbase) * Math.tan(effectiveSteer * RAD) / RAD;
    if (handbrake && Math.abs(speed) > 0.1) yawRate *= config.handbrakeYawBoost;
    yaw = wrapDegrees(yaw + yawRate);

    // The body rotated but momentum did not: the slide angle grows by the turn, then grip
    // pulls the motion back in line with the wheels.
    slip -= yawRate;
    if (handbrake && Math.abs(slip) > config.slideEndDegrees) sliding = true;
    const grip = handbrake ? config.handbrakeGrip : sliding ? config.gripRecovery : 1;
    slip *= 1 - grip;
    slip = Math.max(-config.maxSlideDegrees, Math.min(config.maxSlideDegrees, slip));
    if (!handbrake && Math.abs(slip) <= config.slideEndDegrees) {
      sliding = false;
      slip = 0;
    }
    if (speed === 0) {
      slip = 0;
      sliding = false;
    }
  }

  const motion = headingVector(yaw + slip);
  return {
    state: { speed, yaw, steer, slip, sliding },
    velocity: { x: motion.x * speed, z: motion.z * speed },
  };
}
