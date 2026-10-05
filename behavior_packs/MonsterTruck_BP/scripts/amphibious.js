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

// A rider who sneaks out over liquid is set down on the nearest dry footing within this many blocks of the
// truck. The truck's roof does not hold a player: one set down there falls through into the liquid
// (Client Input Run, docs/agents/bedrock-physics.md).
export const DRY_LAND_REACH = 4;

// Dry footing: a block that is neither air nor liquid, with air at the feet and head above it.
function isDryFooting(dimension, x, y, z) {
  try {
    const below = dimension.getBlock({ x, y: y - 1, z });
    const feet = dimension.getBlock({ x, y, z });
    const head = dimension.getBlock({ x, y: y + 1, z });
    return Boolean(below && !below.isAir && !isLiquidBlock(below.typeId) && feet?.isAir && head?.isAir);
  } catch {
    return false;
  }
}

// The nearest dry footing to a floating truck, as a standing location, or undefined when none is in reach.
// Feet levels from the liquid block the truck floats in up to a bank 2 above the surface, as Shoreline
// Step-Up climbs.
export function findDryLanding(dimension, truckLoc, reach = DRY_LAND_REACH) {
  const cx = Math.floor(truckLoc.x);
  const cz = Math.floor(truckLoc.z);
  const cy = Math.floor(truckLoc.y);
  let best;
  let bestDistance = Infinity;
  for (let x = cx - reach; x <= cx + reach; x++) {
    for (let z = cz - reach; z <= cz + reach; z++) {
      const distance = Math.hypot(x + 0.5 - truckLoc.x, z + 0.5 - truckLoc.z);
      if (distance > reach + 0.5 || distance >= bestDistance) continue;
      for (const y of [cy, cy + 1, cy + 2, cy + 3]) {
        if (isDryFooting(dimension, x, y, z)) {
          best = { x: x + 0.5, y, z: z + 0.5 };
          bestDistance = distance;
          break;
        }
      }
    }
  }
  return best;
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
