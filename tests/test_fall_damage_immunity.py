import json
import shutil
import subprocess
from pathlib import Path

import pytest

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
        pytest.skip("node is not installed")

    script = r'''
import assert from 'node:assert/strict';
import {
  PNEUMATIC_VENT_SOUND,
  PNEUMATIC_DUST_PARTICLE,
  absorbsFallDamage,
  isFalling,
  calculateWheelContactOffsets
} from './behavior_packs/MonsterTruck_BP/scripts/landing.js';

// 1. Audio and particle constants
assert.equal(PNEUMATIC_VENT_SOUND, "random.fizz");
assert.equal(PNEUMATIC_DUST_PARTICLE, "minecraft:campfire_smoke_particle");

// 2. Fall damage absorption predicate
const truck = { id: "truck1", typeId: "blake:monster_truck" };
const rider = { id: "rider1", typeId: "minecraft:player" };
const protectedRiders = new Map([["rider1", "truck1"]]);
assert.equal(absorbsFallDamage("fall", truck, protectedRiders), true, "Truck and riders must absorb fall damage");
assert.equal(absorbsFallDamage("fall", rider, protectedRiders), true, "Truck and riders must absorb fall damage");
assert.equal(absorbsFallDamage("damage.fall", truck, protectedRiders), true, "Bedrock fall cause string must be absorbed");
assert.equal(absorbsFallDamage("entity_attack", truck, protectedRiders), false, "Combat attacks must not be absorbed as fall damage");
assert.equal(absorbsFallDamage("fall", { id: "zombie1", typeId: "minecraft:zombie" }, protectedRiders), false, "Non-riders/non-trucks must not absorb fall damage");

// 3. Fall detection for cliff and ramp drops
assert.equal(isFalling(-0.35, 0), true, "Negative delta Y must be detected as falling");
assert.equal(isFalling(0, -0.40), true, "Negative vertical velocity must be detected as falling");
assert.equal(isFalling(0, 0), false, "Level ground travel must not be detected as falling");

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

# Pneumatic Shock Absorption in play (fall damage cancelled for the truck and for riders only
# during a drop and its landing window, venting and wheel dust on landing, Sneak as the only
# deliberate exit) is behaviour-tested in tests/js/truck_tick.test.mjs and tests/js/main.test.mjs.


def test_script_api_version_supports_required_input_and_before_hurt_events():
    manifest_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    server_dependency = next(
        dep for dep in manifest["dependencies"] if dep.get("module_name") == "@minecraft/server"
    )
    assert server_dependency["version"] == "2.10.0"

    bedrock = json.loads((REPO_ROOT / "testing" / "bedrock.json").read_text(encoding="utf-8"))
    assert bedrock["script_api_version"] == "2.10.0"
    # The held Jump button is the handbrake (ADR-0017): tests/js/main.test.mjs (driverInput).
