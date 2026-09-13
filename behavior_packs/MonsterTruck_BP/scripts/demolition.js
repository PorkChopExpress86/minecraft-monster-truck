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

export function canShearFoliage(hasDriver = true) {
  return Boolean(hasDriver);
}


