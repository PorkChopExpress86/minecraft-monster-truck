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
  calculateSteerAngle,
  sampleGroundHeight
} from "./kinematics.js";
import {
  calculateAquaticImpulse,
  calculateAquaticIntent,
  classifyShorelineColumn,
  calculateShorelineStepImpulse,
  CRUISING_AQUATIC_SPEED
} from "./amphibious.js";
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
  calculateJumpImpulse,
  canTriggerJump,
  calculateCrushStompDamage,
  calculateShockwaveImpulse,
  PNEUMATIC_VENT_SOUND,
  PNEUMATIC_DUST_PARTICLE,
  shouldAbsorbFallDamage,
  isFallingOrAirborne,
  calculateWheelContactOffsets,
  advanceJumpPhase
} from "./suspension.js";

// Track state of each truck across ticks
const truckStates = new Map();
const entityHitCooldowns = new Map();
const protectedRiders = new Map();
const pendingJumpRequests = new Map();
const seatedDriverAssignments = new Map();
let currentTick = 0;
const DIMENSIONS = ["overworld", "nether", "the_end"];

function getCurrentTick() {
  return typeof system.currentTick === "number" ? system.currentTick : currentTick;
}

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
      if (driver) seatedDriverAssignments.set(driver.id, { truckId: truck.id, tick: tickNumber });

      // Dynamic Incline Pitch and Coordinated Four-Wheel Steering updates
      let currentYaw = 0;
      try {
        if (truck.getRotation) {
          currentYaw = truck.getRotation().y;
        }
      } catch {}

      const prevYaw = typeof state.prevYaw === "number" ? state.prevYaw : currentYaw;
      let deltaYaw = ((currentYaw - prevYaw + 540) % 360) - 180;
      state.prevYaw = currentYaw;

      // Update steering angle and sync to property
      state.steerAngle = calculateSteerAngle({
        deltaYaw,
        currentSteer: state.steerAngle || 0,
        hasDriver: Boolean(driver)
      });
      try {
        truck.setProperty("blake:steer_angle", state.steerAngle);
      } catch {}

      // Update dynamic pitch angle and sync to property
      const truckRot = truck.getRotation ? truck.getRotation() : { y: 0 };
      const headRad = (truckRot.y + 90) * (Math.PI / 180);
      const headX = Math.cos(headRad);
      const headZ = Math.sin(headRad);

      const frontX = loc.x + headX * 1.125;
      const frontZ = loc.z + headZ * 1.125;
      const rearX = loc.x - headX * 1.125;
      const rearZ = loc.z - headZ * 1.125;

      const frontHeight = sampleGroundHeight(dimension, frontX, loc.y, frontZ);
      const rearHeight = sampleGroundHeight(dimension, rearX, loc.y, rearZ);
      const verticalVelocity = vel ? vel.y : dy;

      state.pitchAngle = calculateDynamicPitch({
        frontHeight,
        rearHeight,
        currentPitch: state.pitchAngle || 0,
        isAirborne: Boolean(state.isAirborne || state.isFalling),
        inLiquid: inWater || inLava,
        verticalVelocity,
        horizontalSpeed: effectiveSpeed
      });
      try {
        truck.setProperty("blake:pitch_angle", state.pitchAngle);
      } catch {}

      // Aquatic propulsion and Shoreline Step-Up
      if ((inWater || inLava) && driver) {
        const isNonAirNonLiquid = (b) => b && !b.isAir && b.typeId !== "minecraft:air" && !isLiquidBlock(b.typeId);
        const baseY = Math.floor(loc.y);
        let bankFound = null;
        let aquaticIntent = { active: false, heading: { x: dirX, z: dirZ }, throttle: 0 };

        try {
          aquaticIntent = calculateAquaticIntent(
            driver.inputInfo.getMovementVector(),
            { x: dirX, z: dirZ }
          );
        } catch {}

        try {
          const latOffsets = [0, -0.8, 0.8];
          for (const lat of latOffsets) {
            const intentDir = aquaticIntent.active ? aquaticIntent.heading : { x: dirX, z: dirZ };
            const intentPerp = { x: -intentDir.z, z: intentDir.x };
            const checkX = Math.floor(loc.x + intentDir.x * 1.5 + intentPerp.x * lat);
            const checkZ = Math.floor(loc.z + intentDir.z * 1.5 + intentPerp.z * lat);

            const bAtWater = dimension.getBlock({ x: checkX, y: baseY, z: checkZ });
            const bAbove1 = dimension.getBlock({ x: checkX, y: baseY + 1, z: checkZ });
            const bAbove2 = dimension.getBlock({ x: checkX, y: baseY + 2, z: checkZ });
            const bAbove3 = dimension.getBlock({ x: checkX, y: baseY + 3, z: checkZ });

            const solid0 = isNonAirNonLiquid(bAtWater);
            const solid1 = isNonAirNonLiquid(bAbove1);
            const solid2 = isNonAirNonLiquid(bAbove2);
            const solid3 = isNonAirNonLiquid(bAbove3);

            const res = classifyShorelineColumn([solid0, solid1, solid2, solid3]);
            if (res.isShoreline) {
              bankFound = res;
              break;
            }
          }

          if (aquaticIntent.active && bankFound && (!state.lastShorelineStep || tickNumber - state.lastShorelineStep > 12)) {
            state.lastShorelineStep = tickNumber;
            const stepImpulse = calculateShorelineStepImpulse(aquaticIntent.heading, bankFound.stepHeight);
            truck.applyImpulse(stepImpulse);
          } else if (aquaticIntent.active && !state.isAirborne) {
            // Apply propulsion from current Driver input, including from rest.
            const curVel = vel || { x: dx, z: dz };
            const aquaticImpulse = calculateAquaticImpulse(
              curVel,
              aquaticIntent.heading,
              CRUISING_AQUATIC_SPEED * aquaticIntent.throttle
            );
            if (aquaticImpulse.x !== 0 || aquaticImpulse.z !== 0) {
              truck.applyImpulse(aquaticImpulse);
            }
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

      const requestedAt = pendingJumpRequests.get(truck.id);
      const jumpWasRequested = requestedAt !== undefined && tickNumber - requestedAt <= 2;
      const velY = vel ? vel.y : dy;
      const airborneOrFalling = isFallingOrAirborne(Boolean(state.isAirborne), dy, velY);

      // Rider dismount management: differentiate deliberate Sneak (Shift) from Spacebar jump ejection
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
                if (airborneOrFalling && !state.isAirborne) state.isFalling = true;
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

      // Suspension Jump execution (Native engine jump or driver jump key input)
      const NATIVE_JUMP_ASCENT_THRESHOLD = 0.42;
      const isAscending = (vel && vel.y > NATIVE_JUMP_ASCENT_THRESHOLD) || dy > NATIVE_JUMP_ASCENT_THRESHOLD;
      const notStepping = !state.lastShorelineStep || (tickNumber - state.lastShorelineStep > 15);
      const isJumpTriggered = jumpWasRequested || (driver && isAscending && notStepping && !state.isAirborne);
      if (isJumpTriggered && !state.isAirborne &&
          canTriggerJump(state.lastJumpTick, tickNumber) &&
          canTriggerJump(state.lastLandingTick, tickNumber)) {
        pendingJumpRequests.delete(truck.id);
        state.lastJumpTick = tickNumber;
        state.isAirborne = true;
        state.jumpPhase = "launch";
        protectRidersForLifecycle(state, truck.id, prevRiders.length ? prevRiders : state.riders);
        const jImpulse = calculateJumpImpulse(effectiveSpeed, { x: dirX, z: dirZ });
        try { truck.applyImpulse(jImpulse); } catch {}

        // Audio & Particles
        try {
          dimension.playSound("random.fizz", loc, { volume: 1.0, pitch: 0.8 });
          dimension.spawnParticle("minecraft:campfire_smoke_particle", { x: loc.x, y: loc.y + 0.2, z: loc.z });
          if (inWater) {
            dimension.playSound("random.splash", loc, { volume: 1.2, pitch: 0.9 });
            dimension.spawnParticle("minecraft:water_splash_particle", { x: loc.x, y: loc.y + 0.5, z: loc.z });
          } else if (inLava) {
            dimension.playSound("random.fizz", loc, { volume: 1.2, pitch: 0.6 });
            dimension.spawnParticle("minecraft:lava_particle", { x: loc.x, y: loc.y + 0.5, z: loc.z });
            dimension.spawnParticle("minecraft:basic_flame_particle", { x: loc.x, y: loc.y + 0.5, z: loc.z });
          }
        } catch {}
      }

      if (state.isAirborne || state.isFalling ||
          (state.riderRetentionUntil && tickNumber <= state.riderRetentionUntil)) {
        restoreProtectedRiders(state, rideable);
      } else if (state.riderRetentionUntil && tickNumber > state.riderRetentionUntil) {
        clearProtectedRiders(state);
        delete state.riderRetentionUntil;
      }

      // Free-fall and airborne tracking
      if (airborneOrFalling && !state.isAirborne) {
        state.isFalling = true;
        if (!state.protectedRiderIds?.size) {
          protectRidersForLifecycle(state, truck.id, state.riders);
        }
      }



      // Pneumatic Shock Absorption & Landing Detection
      if (state.isAirborne || state.isFalling) {
        const grounded = Boolean(truck.isOnGround);
        const jumpProgress = advanceJumpPhase(state.jumpPhase, {
          verticalVelocity: velY,
          deltaY: dy,
          grounded
        });
        state.jumpPhase = jumpProgress.phase;
        const fallLanded = state.isFalling && !state.isAirborne && grounded && dy <= 0;

        if (jumpProgress.didLand || fallLanded) {
          const wasJump = jumpProgress.didLand;
          state.isAirborne = false;
          state.isFalling = false;
          state.lastLandingTick = tickNumber;
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

          if (wasJump) {
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
      if (canApplyTireTrample(effectiveSpeed, state.isAirborne)) {
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
                2.25,
                3.6,
                1.6
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
      const canWood = canDemolishWood(effectiveSpeed, state.isAirborne);
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

          // Foliage cleared up to 5 blocks high (0..4), wood/glass up to 5 blocks high when airborne, 3 blocks high on ground
          const maxWoodHeight = state.isAirborne ? 5 : 3;
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

if (world.afterEvents && world.afterEvents.playerButtonInput) {
  world.afterEvents.playerButtonInput.subscribe((event) => {
    if (event.button !== InputButton.Jump || event.newButtonState !== ButtonState.Pressed) return;
    try {
      const tick = getCurrentTick();
      let truck = event.player.getComponent("minecraft:riding")?.entityRidingOn;
      if (!truck) {
        const assignment = seatedDriverAssignments.get(event.player.id);
        if (assignment && tick - assignment.tick <= 2) {
          truck = world.getEntity(assignment.truckId);
        }
      }
      if (truck?.typeId === "blake:monster_truck") {
        pendingJumpRequests.set(truck.id, tick);
        system.run(() => {
          try {
            if (truck.isValid && !event.player.isSneaking) {
              truck.getComponent("minecraft:rideable")?.addRider(event.player);
            }
          } catch {}
        });
      }
    } catch {}
  });
}

if (world.beforeEvents && world.beforeEvents.entityHurt) {
  try {
    world.beforeEvents.entityHurt.subscribe((event) => {
      if (isPneumaticallyProtectedFall(event)) {
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
