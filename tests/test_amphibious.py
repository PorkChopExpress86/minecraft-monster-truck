import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_amphibious_buoyancy_configuration():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    assert "minecraft:buoyant" in comps, "Entity must define minecraft:buoyant"
    buoyancy = comps["minecraft:buoyant"]
    
    # Positive buoyancy and liquid targets
    assert buoyancy["base_buoyancy"] >= 1.0, "Must have positive buoyancy"
    assert "liquid_blocks" in buoyancy
    liquids = buoyancy["liquid_blocks"]
    assert "minecraft:water" in liquids
    assert "minecraft:flowing_water" in liquids
    assert "minecraft:lava" in liquids
    assert "minecraft:flowing_lava" in liquids
    
    # Resistance to water currents
    assert comps["minecraft:knockback_resistance"]["value"] == 1.0
    
    # Seated occupants elevated above waterline
    rideable = comps["minecraft:rideable"]
    for seat in rideable["seats"]:
        assert seat["position"][1] >= 0.95, "Seat Y must be elevated above 0.8 waterline"

def test_amphibious_traction_and_navigation_configuration():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    comps = data["minecraft:entity"]["components"]
    
    buoyancy = comps["minecraft:buoyant"]
    assert buoyancy["movement_type"] == "waves", "Native buoyancy must use the engine-supported flotation mode"
    # Driver intent owning liquid traction: tests/js/truck_tick.test.mjs (liquid propulsion).

    nav = comps["minecraft:navigation.walk"]
    assert nav["can_path_over_water"] is True, "Navigation must allow pathing over water"
    assert nav["avoid_water"] is False, "Navigation must not avoid water"

def test_amphibious_physics_helpers_via_node():
    import shutil
    import subprocess
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")
        
    script = r'''
import assert from 'node:assert/strict';
import {
  LIQUID_DRAG_RETENTION,
  classifyShorelineColumn,
  SHORELINE_LIFT,
  shorelineLiftVelocity
} from './behavior_packs/MonsterTruck_BP/scripts/amphibious.js';

// Liquid drag retention measured by Scenario Runs; driving divides its velocity by it so
// liquids are crossed at overland speed (flotation scenarios assert the outcome).
assert.deepEqual(LIQUID_DRAG_RETENTION, { water: 0.86, lava: 0.72 });

// Shoreline detection (Shoreline Step-Up through tickTruck: tests/js/truck_tick.test.mjs).
// The column starts at the submerged bank face, so stepHeight - 1 is the height above the
// surface: flush, 1 and 2 above are shorelines; 3 above is a wall.
assert.deepEqual(classifyShorelineColumn([true, false, false, false]), { isShoreline: true, stepHeight: 1 });
assert.deepEqual(classifyShorelineColumn([true, true, false, false]), { isShoreline: true, stepHeight: 2 });
assert.deepEqual(classifyShorelineColumn([true, true, true, false]), { isShoreline: true, stepHeight: 3 });
assert.deepEqual(classifyShorelineColumn([true, true, true, true]), { isShoreline: false, stepHeight: 4 });

// Shoreline Step-Up lift (held over several ticks through tickTruck: tests/js/truck_tick.test.mjs):
// it climbs at the lift rate, eases in, and never pushes down.
const top = 64;
assert.equal(shorelineLiftVelocity(top - 2.4, top), SHORELINE_LIFT.rate, "far below the top: climb at the lift rate");
assert.ok(shorelineLiftVelocity(top + SHORELINE_LIFT.clearance - 0.1, top) < SHORELINE_LIFT.rate, "eases in near the top");
assert.equal(shorelineLiftVelocity(top + SHORELINE_LIFT.clearance, top), 0, "holds at the top plus clearance");
assert.equal(shorelineLiftVelocity(top + 1, top), 0, "never pushes the truck down");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
