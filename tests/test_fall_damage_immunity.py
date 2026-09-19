import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_entity_pneumatic_shock_absorption_sensor_contract():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    assert "minecraft:damage_sensor" in comps, "Entity must define minecraft:damage_sensor"
    
    triggers = comps["minecraft:damage_sensor"]["triggers"]
    fall_triggers = [t for t in triggers if t.get("cause") == "fall"]
    assert len(fall_triggers) > 0, "Damage sensor must contain a trigger for cause: 'fall'"
    assert fall_triggers[0].get("deals_damage") == "no", "Fall trigger must set deals_damage: 'no'"

def test_pneumatic_shock_absorption_contracts_via_node():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  PNEUMATIC_VENT_SOUND,
  PNEUMATIC_DUST_PARTICLE,
  shouldAbsorbFallDamage,
  isFallingOrAirborne,
  calculateWheelContactOffsets
} from './behavior_packs/MonsterTruck_BP/scripts/suspension.js';

// 1. Audio and particle constants
assert.equal(PNEUMATIC_VENT_SOUND, "random.fizz");
assert.equal(PNEUMATIC_DUST_PARTICLE, "minecraft:campfire_smoke_particle");

// 2. Fall damage absorption predicate
assert.equal(shouldAbsorbFallDamage("fall", true), true, "Truck and riders must absorb fall damage");
assert.equal(shouldAbsorbFallDamage("damage.fall", true), true, "Bedrock fall cause string must be absorbed");
assert.equal(shouldAbsorbFallDamage("entity_attack", true), false, "Combat attacks must not be absorbed as fall damage");
assert.equal(shouldAbsorbFallDamage("fall", false), false, "Non-riders/non-trucks must not absorb fall damage");

// 3. Fall / Airborne state detection across jumps and cliff drops
assert.equal(isFallingOrAirborne(true, 0, 0), true, "Active jump must be treated as airborne");
assert.equal(isFallingOrAirborne(false, -0.35, 0), true, "Negative delta Y must be detected as falling");
assert.equal(isFallingOrAirborne(false, 0, -0.40), true, "Negative vertical velocity must be detected as falling");
assert.equal(isFallingOrAirborne(false, 0, 0), false, "Level ground travel must not be detected as falling");

// 4. Wheel contact points for pneumatic dust cloud dissipation
const wheelOffsets = calculateWheelContactOffsets({ x: 1, z: 0 }, { x: 0, z: 1 }, 1.3, 0.9);
assert.equal(wheelOffsets.length, 4, "Must calculate 4 wheel ground contact positions");
assert.ok(wheelOffsets.some(w => w.x > 0 && w.z > 0), "Front right wheel");
assert.ok(wheelOffsets.some(w => w.x > 0 && w.z < 0), "Front left wheel");
assert.ok(wheelOffsets.some(w => w.x < 0 && w.z > 0), "Rear right wheel");
assert.ok(wheelOffsets.some(w => w.x < 0 && w.z < 0), "Rear left wheel");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

def test_script_pneumatic_shock_absorption_integration():
    main_script = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js"
    assert main_script.exists()
    content = main_script.read_text(encoding="utf-8")
    
    assert "shouldAbsorbFallDamage" in content, "main.js must use shouldAbsorbFallDamage"
    assert "PNEUMATIC_VENT_SOUND" in content, "main.js must reference PNEUMATIC_VENT_SOUND"
    assert "PNEUMATIC_DUST_PARTICLE" in content, "main.js must reference PNEUMATIC_DUST_PARTICLE"
    assert "world.beforeEvents" in content, "main.js must register beforeEvents listener for pneumatic shock absorption"
    assert "recentRiders" not in content, "Fall protection must follow the vehicle event, not a broad time window"
    assert "protectedRiders" in content, "Jump/drop lifecycle must explicitly own rider protection"
    assert content.index("const airborneOrFalling") < content.index("// Rider dismount management")
    assert "if (!player.isSneaking && rideable && rideable.addRider)" in content
    assert "protectRidersForLifecycle(state, truck.id, prevRiders)" in content
    assert "state.isAirborne || state.isFalling ||" in content


def test_script_api_version_supports_required_input_and_before_hurt_events():
    manifest_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    server_dependency = next(
        dep for dep in manifest["dependencies"] if dep.get("module_name") == "@minecraft/server"
    )
    assert server_dependency["version"] == "2.10.0"

    bedrock = json.loads((REPO_ROOT / "testing" / "bedrock.json").read_text(encoding="utf-8"))
    assert bedrock["script_api_version"] == "2.10.0"

    main = (REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js").read_text(encoding="utf-8")
    assert "playerButtonInput" in main
    assert "InputButton.Jump" in main
