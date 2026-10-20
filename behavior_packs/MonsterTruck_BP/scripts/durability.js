// Durability (ADR-0020): the damage a Monster Truck absorbs before it is destroyed. The HUD draws a ridden
// mob's health as hearts, and 1000 health filled ten rows of the rider's view, so the truck's
// minecraft:health is a one-row gauge and the script keeps the real count on the truck.

export const DURABILITY = 1000;
// minecraft:health max in monster_truck.entity.json: 10 mount hearts.
export const GAUGE_HEALTH = 20;
export const DURABILITY_PROPERTY = "blake:durability";

// The armored chassis takes a quarter of combat and explosion damage; fall damage never reaches it
// (Pneumatic Shock Absorption). Every other cause costs its full damage.
const DAMAGE_MULTIPLIERS = {
  entityAttack: 0.25,
  projectile: 0.25,
  entityExplosion: 0.25,
  blockExplosion: 0.25,
  fall: 0,
};

// A hit within this many ticks of the last costly one costs only what it exceeds that hit by, as the engine's
// damage immunity window does (docs/agents/bedrock-physics.md "Damage immunity window"). The handler cancels
// the engine's damage, so the engine opens no window of its own and lava would otherwise cost every tick.
export const IMMUNITY_TICKS = 10;

/**
 * Durability one hit costs. `state` keeps the immunity window between calls.
 * @param {{ lastHitTick?: number, lastHitCost?: number }} state
 * @param {string | undefined} cause
 * @param {number} damage
 * @param {number} tick
 */
export function hitCost(state, cause, damage, tick) {
  const cost = Math.max(0, damage) * (DAMAGE_MULTIPLIERS[cause] ?? 1);
  if (state.lastHitTick !== undefined && tick - state.lastHitTick < IMMUNITY_TICKS) {
    const excess = cost - state.lastHitCost;
    if (excess <= 0) return 0;
    state.lastHitCost = cost;
    return excess;
  }
  if (cost > 0) {
    state.lastHitTick = tick;
    state.lastHitCost = cost;
  }
  return cost;
}

/** The gauge's health for the Durability left: never 0, which would kill the truck. */
export function gaugeHealth(durability) {
  return Math.max(1, Math.ceil((durability * GAUGE_HEALTH) / DURABILITY));
}
