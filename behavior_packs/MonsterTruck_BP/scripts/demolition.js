// Hard material exclusions: demolition must never destroy these materials
export const HARD_EXCLUSIONS = [
  "iron", "stone", "cobblestone", "brick", "granite", "diorite", "andesite",
  "deepslate", "blackstone", "obsidian", "metal", "copper", "gold", "diamond",
  "netherite", "prismarine", "sandstone", "quartz", "purpur", "end_stone",
  "terracotta", "concrete", "bedrock", "dirt", "mud", "sand", "gravel"
];

// Structural wood keywords
export const WOOD_KEYWORDS = [
  "log", "wood", "stem", "hyphae", "planks", "fence", "gate",
  "door", "trapdoor", "stairs", "slab"
];

export function isFoliage(typeId) {
  if (!typeId) return false;
  const id = typeId.replace("minecraft:", "").toLowerCase();
  return (
    id.includes("leaves") ||
    id.includes("vine") ||
    id === "grass" ||
    id === "tall_grass" ||
    id.includes("fern") ||
    id.includes("sapling") ||
    id.includes("flower") ||
    id.includes("bush") ||
    id.includes("azalea") ||
    id.includes("hanging_roots") ||
    id.includes("spore_blossom")
  );
}

export function isDestructibleWoodOrGlass(typeId) {
  if (!typeId) return false;
  const id = typeId.replace("minecraft:", "").toLowerCase();

  for (const exclusion of HARD_EXCLUSIONS) {
    if (id.includes(exclusion)) return false;
  }

  if (id.includes("glass")) return true;

  return WOOD_KEYWORDS.some((kw) => id.includes(kw));
}

export const WOOD_MOMENTUM_THRESHOLD = 0.25;

export function canDemolishWood(effectiveSpeed, isAirborne = false) {
  return isAirborne || effectiveSpeed > WOOD_MOMENTUM_THRESHOLD;
}

/**
 * Clear what is in front of the truck this tick: Foliage Shearing (no drops) whenever a driver
 * is seated, Wood Demolition (survival drops) above WOOD_MOMENTUM_THRESHOLD.
 * @param {import("./truck_tick.js").WorldDimension} dimension
 * @param {{
 *   location: import("./truck_tick.js").Vector3,
 *   heading: { x: number, z: number },
 *   speed: number,
 *   hasDriver: boolean,
 * }} ahead heading: unit direction of travel; speed: blocks/tick.
 */
export function demolishAhead(dimension, { location: loc, heading, speed, hasDriver }) {
  const canWood = canDemolishWood(speed);
  const canFoliage = Boolean(hasDriver);

  if (!canWood && !canFoliage) {
    return;
  }

  const dirX = heading.x;
  const dirZ = heading.z;
  const perpX = -dirZ;
  const perpZ = dirX;
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


