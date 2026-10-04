// Amphibious flotation and shoreline step-up physics for Monster Truck. Propulsion on
// liquids is the same script-driven driving as on land (driving.js, ADR-0017).

// Share of velocity a floating truck keeps after the engine's liquid drag, measured by
// Scenario Runs (#38): a 1.1 velocity moved it 0.95 blocks/tick in water, 0.79 in lava.
// Driving divides its target velocity by this so liquids are crossed at overland speed.
export const LIQUID_DRAG_RETENTION = { water: 0.86, lava: 0.72 };

export function isLiquidBlock(typeId) {
  if (!typeId) return false;
  const id = typeId.replace("minecraft:", "").toLowerCase();
  return id === "water" || id === "flowing_water" || id === "lava" || id === "flowing_lava";
}

// Where a rider who sneaks out over liquid is set down: on the cab roof / rear flatbed.
export function getSafeDismountLocation(truckLoc, heading = { x: 1, z: 0 }) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  return {
    x: truckLoc.x - dirX * 0.8,
    y: truckLoc.y + 2.3,
    z: truckLoc.z - dirZ * 0.8,
  };
}

// solidColumn[0] is the bank block level with the liquid block the truck floats in (below the
// surface), then the blocks above it. A bank is a shoreline when its top is at most 2 blocks above
// the liquid surface (stepHeight 1-3: flush, 1 above, 2 above); 3 or more above is a wall.
export function classifyShorelineColumn(solidColumn = []) {
  let stepHeight = 0;
  for (const solid of solidColumn) {
    if (!solid) break;
    stepHeight += 1;
  }

  return {
    isShoreline: stepHeight >= 1 && stepHeight <= 3,
    stepHeight
  };
}

export function calculateShorelineStepImpulse(heading = { x: 1, z: 0 }, stepHeight = 1) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

  if (stepHeight >= 3) {
    return {
      x: dirX * 0.45,
      // A bank 2 above the surface. shoreline_step2 measured (water/lava peaks): 0.75 -> +2.27 in
      // water on the first lift; in lava most lifts top out near +0.5-0.8 whatever the value
      // (0.75-1.05), so lava climbs only on a later lift. 0.78 -> +2.45 in water, near a launch.
      y: 0.75,
      z: dirZ * 0.45,
    };
  }

  if (stepHeight >= 2) {
    return {
      x: dirX * 0.40,
      y: 0.62, // Elevates cleanly over 2-block shoreline rise
      z: dirZ * 0.40,
    };
  }

  return {
    x: dirX * 0.35,
    y: 0.42, // Elevates cleanly over 1-block shoreline rise
    z: dirZ * 0.35,
  };
}

// Thermal shielding: riders seated in the truck take no heat damage while it crosses lava
// or climbs out of it, including the moment the seat dips into the lava surface.
const HEAT_DAMAGE_CAUSES = new Set(["fire", "fireTick", "lava"]);

export function shouldShieldRiderFromHeat(damageCause, isSeatedRider = false) {
  return Boolean(isSeatedRider) && HEAT_DAMAGE_CAUSES.has(damageCause);
}
