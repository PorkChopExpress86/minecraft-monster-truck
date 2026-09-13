import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_lava_damage_immunity_and_buoyancy():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    # 1. Damage sensor immunities
    sensor = comps["minecraft:damage_sensor"]
    triggers = sensor["triggers"]
    
    fire_trigger = next((t for t in triggers if t.get("cause") == "fire"), None)
    fire_tick_trigger = next((t for t in triggers if t.get("cause") == "fire_tick"), None)
    lava_trigger = next((t for t in triggers if t.get("cause") == "lava"), None)
    
    assert fire_trigger is not None, "Must have fire damage trigger"
    assert fire_trigger.get("deals_damage") == "no"
    assert fire_tick_trigger is not None, "Must have fire_tick damage trigger"
    assert fire_tick_trigger.get("deals_damage") == "no"
    assert lava_trigger is not None, "Must have lava damage trigger"
    assert lava_trigger.get("deals_damage") == "no"
    
    # 2. Lava buoyancy
    buoyancy = comps["minecraft:buoyant"]
    liquids = buoyancy["liquid_blocks"]
    assert "minecraft:lava" in liquids
    assert "minecraft:flowing_lava" in liquids

def test_safe_dismount_and_liquid_helpers():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  isLiquidBlock,
  getSafeDismountLocation
} from './behavior_packs/MonsterTruck_BP/scripts/trample.js';

// Liquid checks
assert.ok(isLiquidBlock("minecraft:water"));
assert.ok(isLiquidBlock("minecraft:flowing_water"));
assert.ok(isLiquidBlock("minecraft:lava"));
assert.ok(isLiquidBlock("minecraft:flowing_lava"));
assert.ok(!isLiquidBlock("minecraft:air"));
assert.ok(!isLiquidBlock("minecraft:stone"));

// Safe dismount location
const truckLoc = { x: 100, y: 64, z: 100 };
const dismountPos = getSafeDismountLocation(truckLoc);
assert.ok(dismountPos.y > truckLoc.y + 1.5, "Safe dismount must place rider on roof/bed height");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
