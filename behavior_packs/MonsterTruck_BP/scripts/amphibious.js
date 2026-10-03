// Amphibious flotation and shoreline step-up physics for Monster Truck. Propulsion on
// liquids is the same script-driven driving as on land (driving.js, ADR-0017).

// Share of velocity a floating truck keeps after the engine's liquid drag, measured by
// Scenario Runs (#38): a 1.1 velocity moved it 0.95 blocks/tick in water, 0.79 in lava.
// Driving divides its target velocity by this so liquids are crossed at overland speed.
export const LIQUID_DRAG_RETENTION = { water: 0.86, lava: 0.72 };

export function detectShorelineBank(
  inLiquid = false,
  frontBlockAtWaterIsSolid = false,
  frontBlockAboveIsSolid = false
) {
  if (!inLiquid || !frontBlockAtWaterIsSolid) {
    return { isShoreline: false, stepHeight: 0 };
  }

  const stepHeight = frontBlockAboveIsSolid ? 2 : 1;
  return {
    isShoreline: true,
    stepHeight,
  };
}

export function classifyShorelineColumn(solidColumn = []) {
  let stepHeight = 0;
  for (const solid of solidColumn) {
    if (!solid) break;
    stepHeight += 1;
  }

  return {
    isShoreline: stepHeight === 1 || stepHeight === 2,
    stepHeight
  };
}

export function calculateShorelineStepImpulse(heading = { x: 1, z: 0 }, stepHeight = 1) {
  const hDist = Math.hypot(heading.x, heading.z) || 1;
  const dirX = heading.x / hDist;
  const dirZ = heading.z / hDist;

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
