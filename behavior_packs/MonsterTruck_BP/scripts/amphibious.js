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

// Shoreline Step-Up lift, held while the truck is against a qualifying bank and below its top.
// The engine moves the truck by the velocity set the tick before and only then applies drag, so
// a lift set every tick rises the same in water and lava; a single impulse does not, because
// after the first move lava kept only 0.04-0.32 of the lift on 4 of 5 lifts and 0.79 on the
// other (water: 0.71) (docs/agents/bedrock-physics.md).
// rate: blocks/tick of climb; clearance: how far above the bank top the bottom is held until the
// truck is over the bank; maxTicks: when an unfinished lift gives up.
export const SHORELINE_LIFT = { rate: 0.5, clearance: 0.2, maxTicks: 20 };

// Vertical velocity for this tick of the lift: climb at the lift rate, easing in so the truck's
// bottom settles at the bank top plus clearance instead of overshooting.
export function shorelineLiftVelocity(truckY, bankTopY, config = SHORELINE_LIFT) {
  return Math.max(0, Math.min(config.rate, bankTopY + config.clearance - truckY));
}

// Thermal shielding: riders seated in the truck take no heat damage while it crosses lava
// or climbs out of it, including the moment the seat dips into the lava surface.
const HEAT_DAMAGE_CAUSES = new Set(["fire", "fireTick", "lava"]);

export function shouldShieldRiderFromHeat(damageCause, isSeatedRider = false) {
  return Boolean(isSeatedRider) && HEAT_DAMAGE_CAUSES.has(damageCause);
}
