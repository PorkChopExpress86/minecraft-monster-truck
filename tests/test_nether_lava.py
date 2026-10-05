import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_lava_travel_and_catastrophic_hazard_damage():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    # 1. Fire and lava can eventually destroy the truck and therefore follow
    # the catastrophic Scrap path; only the seated riders receive shielding.
    sensor = comps["minecraft:damage_sensor"]
    triggers = sensor["triggers"]
    
    fire_trigger = next((t for t in triggers if t.get("cause") == "fire"), None)
    fire_tick_trigger = next((t for t in triggers if t.get("cause") == "fire_tick"), None)
    lava_trigger = next((t for t in triggers if t.get("cause") == "lava"), None)
    
    assert fire_trigger is not None, "Must have fire damage trigger"
    assert fire_trigger.get("deals_damage") == "yes"
    assert fire_tick_trigger is not None, "Must have fire_tick damage trigger"
    assert fire_tick_trigger.get("deals_damage") == "yes"
    assert lava_trigger is not None, "Must have lava damage trigger"
    assert lava_trigger.get("deals_damage") == "yes"
    
    # 2. Lava buoyancy
    buoyancy = comps["minecraft:buoyant"]
    liquids = buoyancy["liquid_blocks"]
    assert "minecraft:lava" in liquids
    assert "minecraft:flowing_lava" in liquids

def test_safe_dismount_and_liquid_helpers():
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")

    script = r'''
import assert from 'node:assert/strict';
import {
  isLiquidBlock,
  findDryLanding
} from './behavior_packs/MonsterTruck_BP/scripts/amphibious.js';

// Liquid checks
assert.ok(isLiquidBlock("minecraft:water"));
assert.ok(isLiquidBlock("minecraft:flowing_water"));
assert.ok(isLiquidBlock("minecraft:lava"));
assert.ok(isLiquidBlock("minecraft:flowing_lava"));
assert.ok(!isLiquidBlock("minecraft:air"));
assert.ok(!isLiquidBlock("minecraft:stone"));

// Sneak exit over liquid: the nearest dry footing (solid below, air at feet and head), or none.
const lavaLake = (y) => (y <= 64 ? "minecraft:lava" : "minecraft:air");
const shore = { getBlock: ({ x, y }) => {
  const typeId = x >= 102 ? (y <= 64 ? "minecraft:netherrack" : "minecraft:air") : lavaLake(y);
  return { typeId, isAir: typeId === "minecraft:air" };
} };
const truckLoc = { x: 100.5, y: 64.6, z: 100.5 };
assert.deepEqual(findDryLanding(shore, truckLoc), { x: 102.5, y: 65, z: 100.5 }, "netherrack bank beside the lava");
assert.equal(findDryLanding({ getBlock: ({ y }) => ({ typeId: lavaLake(y), isAir: y > 64 }) }, truckLoc), undefined,
             "no dry land in reach");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
