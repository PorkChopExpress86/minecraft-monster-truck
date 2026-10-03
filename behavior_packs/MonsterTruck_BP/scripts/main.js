import {
  system,
  world,
  ButtonState,
  EntityDamageCause,
  InputButton,
  ItemStack
} from "@minecraft/server";
import { isFoliage, isDestructibleWoodOrGlass, canDemolishWood, canShearFoliage } from "./demolition.js";
import {
  calculateDynamicPitch,
  sampleGroundHeight
} from "./kinematics.js";
import {
  classifyShorelineColumn,
  calculateShorelineStepImpulse,
  LIQUID_DRAG_RETENTION,
  shouldShieldRiderFromHeat
} from "./amphibious.js";
import { createDrivingState, groundRetention, headingVector, stepDriving } from "./driving.js";
import { AXLE_OFFSET, CONTACT_PERIMETER, TRUCK_LENGTH, TRUCK_WIDTH } from "./geometry.js";
import {
  calculateTrampleDamage,
  canApplyTireTrample,
  isInContactPerimeter,
  calculateKnockbackImpulse,
  isProtectedTarget,
  isHeavyEntity,
  resolveHeavyCollision,
  isLiquidBlock,
  getSafeDismountLocation
} from "./trample.js";
import {
  calculateCrushStompDamage,
  calculateShockwaveImpulse,
  isCrushStompLanding,
  PNEUMATIC_VENT_SOUND,
  PNEUMATIC_DUST_PARTICLE,
  shouldAbsorbFallDamage,
  isFalling,
  calculateWheelContactOffsets
} from "./suspension.js";

// Track state of each truck across ticks
const truckStates = new Map();
const entityHitCooldowns = new Map();
const protectedRiders = new Map();
const AIR_DRAG_RETENTION = 0.91; // horizontal velocity kept per tick while airborne
let currentTick = 0;
const DIMENSIONS = ["overworld", "nether", "the_end"];

// Driver input: movement ({ x: strafe, y: forward }) and the held Jump button, which is the
// handbrake. Exported so Scenario Runs can supply the input a Simulated Driver's inputInfo
// never reports (ADR-0016).
export const driverInput = {
  movement: (driver) => driver.inputInfo.getMovementVector(),
  handbrake: (driver) => driver.inputInfo.getButtonState(InputButton.Jump) === ButtonState.Pressed,
};

function protectRidersForLifecycle(state, truckId, riderIds) {
  state.protectedRiderIds = new Set(riderIds);
  for (const riderId of state.protectedRiderIds) {
    protectedRiders.set(riderId, truckId);
  }
}

function clearProtectedRiders(state) {
  for (const riderId of state.protectedRiderIds || []) {
    protectedRiders.delete(riderId);
  }
  state.protectedRiderIds = new Set();
}

function restoreProtectedRiders(state, rideable) {
  if (!rideable?.addRider || !state.protectedRiderIds?.size) return;
  const seated = new Set((rideable.getRiders?.() || []).map((rider) => rider.id));
  for (const riderId of state.protectedRiderIds) {
    if (seated.has(riderId)) continue;
    try {
      const rider = world.getEntity(riderId);
      if (rider?.isValid && rider.typeId === "minecraft:player" && !rider.isSneaking) {
        rideable.addRider(rider);
      }
    } catch {}
  }
}

function onTick() {
  for (const dimName of DIMENSIONS) {
    let dimension;
    try {
      dimension = world.getDimension(dimName);
    } catch {
      continue;
    }
    if (!dimension) continue;

    let trucks;
    try {
      trucks = dimension.getEntities({ type: "blake:monster_truck" });
    } catch {
      continue;
    }

    for (const truck of trucks) {
      if (!truck || !truck.isValid) continue;

      const loc = truck.location;
      const state = truckStates.get(truck.id) || {
        prevX: loc.x,
        prevY: loc.y,
        prevZ: loc.z,
      };

      const dx = loc.x - state.prevX;
      const dy = loc.y - state.prevY;
      const dz = loc.z - state.prevZ;

      // Update state for next tick
      state.prevX = loc.x;
      state.prevY = loc.y;
      state.prevZ = loc.z;
      truckStates.set(truck.id, state);

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
      const tickNumber = typeof system.currentTick === "number" ? system.currentTick : currentTick++;

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
      const currentRiders = rideable && rideable.getRiders ? rideable.getRiders() : [];
      const prevRiders = state.riders || [];
      state.riders = currentRiders.map((r) => r.id);

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
        state.moltenUntil = tickNumber + 200; // 10s molten tire trample upon exiting lava
        for (const rider of currentRiders) {
          try {
            if (rider.extinguishFire) rider.extinguishFire(false);
          } catch {}
        }
      }

      const driver = currentRiders.length > 0 ? currentRiders[0] : undefined;

      // Script-driven driving (ADR-0017): W/S throttle, A/D steer the wheels, Jump held is
      // the handbrake. The truck's yaw is owned here; the driver's mouse only moves the camera.
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
      // the bank's edge while it rises.
      const steppingAshore = state.lastShorelineStep !== undefined && tickNumber - state.lastShorelineStep < 8;
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

      // Update dynamic pitch angle and sync to property
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
      const verticalVelocity = vel ? vel.y : dy;

      state.pitchAngle = calculateDynamicPitch({
        frontHeight,
        rearHeight,
        currentPitch: state.pitchAngle || 0,
        isAirborne: Boolean(state.isFalling),
        inLiquid: inWater || inLava,
        verticalVelocity,
        horizontalSpeed: effectiveSpeed
      });
      try {
        truck.setProperty("blake:pitch_angle", state.pitchAngle);
      } catch {}

      // Shoreline Step-Up: driving forward against a 1-2 block bank lifts the truck out.
      // Propulsion on liquids is the driving above.
      if (inLiquid && driver && (driverControls.forward ?? 0) > 0.05) {
        const isNonAirNonLiquid = (b) => b && !b.isAir && b.typeId !== "minecraft:air" && !isLiquidBlock(b.typeId);
        const baseY = Math.floor(loc.y);
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

          if (bankFound && (!state.lastShorelineStep || tickNumber - state.lastShorelineStep > 12)) {
            state.lastShorelineStep = tickNumber;
            truck.applyImpulse(calculateShorelineStepImpulse(intentDir, bankFound.stepHeight));
          }
        } catch {}
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

      const velY = vel ? vel.y : dy;
      const falling = isFalling(dy, velY);

      // Rider dismount management: Sneak (Shift) is the only deliberate exit
      if (prevRiders.length > currentRiders.length) {
        const currentRiderIds = new Set(currentRiders.map((r) => r.id));
        const dismountedIds = prevRiders.filter((id) => !currentRiderIds.has(id));
        const safePos = getSafeDismountLocation(loc, { x: dirX, z: dirZ });
        for (const playerId of dismountedIds) {
          try {
            const player = world.getEntity(playerId);
            if (player && player.isValid && player.typeId === "minecraft:player") {
              if (!player.isSneaking && rideable && rideable.addRider) {
                // Sneak is the only deliberate exit. Keep any other engine
                // detachment tied to a bounded vehicle lifecycle.
                if (!state.protectedRiderIds?.size) {
                  protectRidersForLifecycle(state, truck.id, prevRiders);
                }
                state.riderRetentionUntil = tickNumber + 8;
                if (falling && !state.isFalling) {
                  state.isFalling = true;
                  state.fallStartY = loc.y - dy;
                }
                rideable.addRider(player);
              } else if (inLava || inWater) {
                // Deliberate sneak dismount over liquid: teleport to safe shoreline
                player.teleport(safePos, { dimension });
                protectedRiders.delete(playerId);
                state.protectedRiderIds?.delete(playerId);
              } else {
                protectedRiders.delete(playerId);
                state.protectedRiderIds?.delete(playerId);
              }
            }
          } catch {}
        }
      }

      if (state.isFalling ||
          (state.riderRetentionUntil && tickNumber <= state.riderRetentionUntil)) {
        restoreProtectedRiders(state, rideable);
      } else if (state.riderRetentionUntil && tickNumber > state.riderRetentionUntil) {
        clearProtectedRiders(state);
        delete state.riderRetentionUntil;
      }

      // Free-fall tracking: remember where the drop began for Crush Stomp
      if (falling && !state.isFalling) {
        state.isFalling = true;
        state.fallStartY = loc.y - dy;
        if (!state.protectedRiderIds?.size) {
          protectRidersForLifecycle(state, truck.id, state.riders);
        }
      }

      // Pneumatic Shock Absorption & Landing Detection
      if (state.isFalling) {
        const grounded = Boolean(truck.isOnGround);
        if (grounded && dy <= 0) {
          const crushes = isCrushStompLanding((state.fallStartY ?? loc.y) - loc.y);
          state.isFalling = false;
          state.riderRetentionUntil = tickNumber + 8;

          // Dissipate impact energy with pneumatic venting audio and quad wheel dust particles
          try {
            dimension.playSound(PNEUMATIC_VENT_SOUND, loc, { volume: 1.0, pitch: 0.85 });
            const wheelOffsets = calculateWheelContactOffsets({ x: dirX, z: dirZ }, { x: perpX, z: perpZ });
            for (const offset of wheelOffsets) {
              dimension.spawnParticle(PNEUMATIC_DUST_PARTICLE, {
                x: loc.x + offset.x,
                y: loc.y + 0.15,
                z: loc.z + offset.z
              });
            }
          } catch {}

          if (crushes) {
            const crushDamage = calculateCrushStompDamage();
            try {
              const nearby = dimension.getEntities({ location: loc, maxDistance: 3.5 });
              for (const target of nearby) {
                if (isProtectedTarget(target, truck)) continue;

                const shockImpulse = calculateShockwaveImpulse(target.location, loc, 1.5);
                try { target.applyImpulse(shockImpulse); } catch {}

                const damageOptions = {};
                if (typeof EntityDamageCause !== "undefined" && EntityDamageCause?.contact) {
                  damageOptions.cause = EntityDamageCause.contact;
                }
                damageOptions.damagingEntity = truck;
                try { target.applyDamage(crushDamage, damageOptions); } catch {
                  try { target.applyDamage(crushDamage); } catch {}
                }
              }

              dimension.playSound("random.explode", loc, { volume: 0.8, pitch: 1.4 });
              dimension.spawnParticle("minecraft:large_explosion", { x: loc.x, y: loc.y + 0.3, z: loc.z });
            } catch {}
          }
        }
      }

      // Tire trample check (within 1.6 blocks contact perimeter)
      if (canApplyTireTrample(effectiveSpeed, false)) {
        try {
          const nearbyEntities = dimension.getEntities({
            location: loc,
            maxDistance: 4.5,
          });

          for (const target of nearbyEntities) {
            if (isProtectedTarget(target, truck)) continue;

            if (
              isInContactPerimeter(
                target.location,
                loc,
                { x: dirX, z: dirZ },
                TRUCK_WIDTH,
                TRUCK_LENGTH,
                CONTACT_PERIMETER
              )
            ) {
              const lastHit = entityHitCooldowns.get(target.id) || 0;
              if (tickNumber - lastHit < 6) continue;
              entityHitCooldowns.set(target.id, tickNumber);

              if (isHeavyEntity(target)) {
                const heavyRes = resolveHeavyCollision(effectiveSpeed, { x: dirX, z: dirZ });
                if (heavyRes.truckHalted) {
                  try {
                    truck.clearVelocity();
                    truck.applyImpulse(heavyRes.truckPenaltyImpulse);
                  } catch {}
                  state.prevX = loc.x;
                  state.prevY = loc.y;
                  state.prevZ = loc.z;
                } else if (heavyRes.targetShoved) {
                  try {
                    target.applyImpulse(heavyRes.targetImpulse);
                    truck.applyImpulse(heavyRes.truckPenaltyImpulse);
                  } catch {}
                }

                const damage = heavyRes.damage;
                if (damage > 0) {
                  const damageOptions = {};
                  if (typeof EntityDamageCause !== "undefined" && EntityDamageCause?.entityAttack) {
                    damageOptions.cause = EntityDamageCause.entityAttack;
                  }
                  damageOptions.damagingEntity = truck;
                  try {
                    target.applyDamage(damage, damageOptions);
                  } catch {
                    try { target.applyDamage(damage); } catch {}
                  }

                  // Molten Tire Trample ignition on heavy entity
                  if (state.moltenUntil && tickNumber < state.moltenUntil) {
                    try {
                      target.setOnFire(6, true);
                    } catch {}
                  }
                }
              } else {
                // Regular trample knockback and damage without halting the truck
                const damage = calculateTrampleDamage(effectiveSpeed);
                if (damage > 0) {
                  const impulse = calculateKnockbackImpulse(
                    target.location,
                    loc,
                    effectiveSpeed
                  );
                  try {
                    target.applyImpulse(impulse);
                  } catch {}

                  const damageOptions = {};
                  if (
                    typeof EntityDamageCause !== "undefined" &&
                    EntityDamageCause?.entityAttack
                  ) {
                    damageOptions.cause = EntityDamageCause.entityAttack;
                  }
                  damageOptions.damagingEntity = truck;

                  try {
                    target.applyDamage(damage, damageOptions);
                  } catch {
                    try {
                      target.applyDamage(damage);
                    } catch {}
                  }

                  // Molten Tire Trample ignition
                  if (state.moltenUntil && tickNumber < state.moltenUntil) {
                    try {
                      target.setOnFire(6, true);
                    } catch {}
                  }
                }
              }
            }
          }
        } catch {}
      }

      // Foliage shearing at any speed with driver; structural wood requires > 0.25 momentum
      const hasDriver = Boolean(driver);
      const canWood = canDemolishWood(effectiveSpeed);
      const canFoliage = canShearFoliage(hasDriver);

      if (!canWood && !canFoliage) {
        continue;
      }

      const sampledBlocks = new Set();
      const forwardDistances = [0.0, 0.6, 1.2, 1.8, 2.5];
      const lateralOffsets = [-1.2, -0.6, 0.0, 0.6, 1.2];
      const baseY = Math.floor(loc.y + 0.05);

      for (const fwd of forwardDistances) {
        for (const lat of lateralOffsets) {
          const px = Math.floor(loc.x + dirX * fwd + perpX * lat);
          const pz = Math.floor(loc.z + dirZ * fwd + perpZ * lat);

          // Foliage cleared up to 5 blocks high (0..4), wood/glass up to 3 blocks high
          const maxWoodHeight = 3;
          for (let h = 0; h < 5; h++) {
            const py = baseY + h;
            const key = `${px},${py},${pz}`;
            if (sampledBlocks.has(key)) continue;
            sampledBlocks.add(key);

            try {
              const block = dimension.getBlock({ x: px, y: py, z: pz });
              if (!block || block.isAir || block.typeId === "minecraft:air") continue;

              const typeId = block.typeId;

              // Foliage vaporization (clean without item drops - active at any speed with driver)
              if (canFoliage && isFoliage(typeId)) {
                block.setType("minecraft:air");
              }
              // Structural wood & glass demolition (drops survival items, plays break sound/particles)
              else if (canWood && h < maxWoodHeight && isDestructibleWoodOrGlass(typeId)) {
                dimension.runCommand(`setblock ${px} ${py} ${pz} air destroy`);
              }
            } catch {
              // Ignore blocks outside active simulation
            }
          }
        }
      }
    }
  }
}

// Subscribe tick loop
system.runInterval(onTick, 1);

// Pneumatic Shock Absorption event handling for vehicle and riders
function isPneumaticallyProtectedFall(event) {
  const cause = event.damageSource ? event.damageSource.cause : undefined;
  const hurtEntity = event.hurtEntity;
  if (!hurtEntity) return false;

  const isTruck = hurtEntity.typeId === "blake:monster_truck";
  const isRider = protectedRiders.has(hurtEntity.id);
  return shouldAbsorbFallDamage(cause, isTruck || isRider);
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
