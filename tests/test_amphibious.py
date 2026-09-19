import json
from pathlib import Path

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

    main = (REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js").read_text(encoding="utf-8")
    assert "driver.inputInfo.getMovementVector()" in main, "Scripted Driver intent owns horizontal liquid traction"
    
    nav = comps["minecraft:navigation.walk"]
    assert nav["can_path_over_water"] is True, "Navigation must allow pathing over water"
    assert nav["avoid_water"] is False, "Navigation must not avoid water"

def test_amphibious_physics_helpers_via_node():
    import shutil
    import subprocess
    node_exe = shutil.which("node")
    if not node_exe:
        return
        
    script = r'''
import assert from 'node:assert/strict';
import {
  CRUISING_AQUATIC_SPEED,
  calculateAquaticImpulse,
  calculateAquaticIntent,
  classifyShorelineColumn,
  detectShorelineBank,
  calculateShorelineStepImpulse
} from './behavior_packs/MonsterTruck_BP/scripts/amphibious.js';

// Speed target contract
assert.equal(CRUISING_AQUATIC_SPEED, 0.55);

// Aquatic forward impulse from standstill
const impulseFromStop = calculateAquaticImpulse({ x: 0, z: 0 }, { x: 1, z: 0 }, 0.55);
assert.ok(impulseFromStop.x > 0.1, "Impulse should push forward when speed is below 0.55");
assert.equal(impulseFromStop.y, 0, "No vertical impulse during cruising");
assert.equal(impulseFromStop.z, 0);

// Zero impulse when already at cruising speed
const impulseAtSpeed = calculateAquaticImpulse({ x: 0.55, z: 0 }, { x: 1, z: 0 }, 0.55);
assert.equal(impulseAtSpeed.x, 0, "No added impulse when already at full speed");

// Player movement intent, not existing momentum, owns liquid propulsion.
const forwardIntent = calculateAquaticIntent({ x: 0, y: 1 }, { x: 1, z: 0 });
assert.equal(forwardIntent.active, true);
assert.deepEqual(forwardIntent.heading, { x: 1, z: 0 });
const steeringIntent = calculateAquaticIntent({ x: 1, y: 0 }, { x: 1, z: 0 });
assert.equal(steeringIntent.active, true);
assert.ok(steeringIntent.heading.z > 0, "Lateral input must steer away from stale momentum");
assert.equal(calculateAquaticIntent({ x: 0, y: 0 }, { x: 1, z: 0 }).active, false,
  "Released controls must stop adding propulsion");

// Shoreline detection
assert.equal(detectShorelineBank(true, true, false).isShoreline, true);
assert.equal(detectShorelineBank(true, true, false).stepHeight, 1);
assert.equal(detectShorelineBank(true, true, true).stepHeight, 2);
assert.equal(detectShorelineBank(false, true, false).isShoreline, false, "Not shoreline if truck is not in liquid");
assert.equal(detectShorelineBank(true, false, false).isShoreline, false, "Not shoreline if front block is liquid/air");
assert.deepEqual(classifyShorelineColumn([true, false, false, false]), { isShoreline: true, stepHeight: 1 });
assert.deepEqual(classifyShorelineColumn([true, true, false, false]), { isShoreline: true, stepHeight: 2 });
assert.deepEqual(classifyShorelineColumn([true, true, true, false]), { isShoreline: false, stepHeight: 3 });
assert.deepEqual(classifyShorelineColumn([true, true, true, true]), { isShoreline: false, stepHeight: 4 });

// Shoreline step impulse calculation
const step1 = calculateShorelineStepImpulse({ x: 1, z: 0 }, 1);
assert.ok(step1.y >= 0.35, "1-block step requires vertical lift");
assert.ok(step1.x >= 0.25, "1-block step requires forward push");

const step2 = calculateShorelineStepImpulse({ x: 0, z: 1 }, 2);
assert.ok(step2.y > step1.y, "2-block step requires higher vertical lift than 1-block");
assert.ok(step2.z >= 0.3, "2-block step requires forward push");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
