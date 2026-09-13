import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_heavy_collision_contracts():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  isHeavyEntity,
  resolveHeavyCollision
} from './behavior_packs/MonsterTruck_BP/scripts/trample.js';

// 1. Heavy entity detection
assert.ok(isHeavyEntity({ typeId: "minecraft:iron_golem" }));
assert.ok(isHeavyEntity({ typeId: "minecraft:warden" }));
assert.ok(!isHeavyEntity({ typeId: "minecraft:zombie" }));
assert.ok(!isHeavyEntity({ typeId: "minecraft:skeleton" }));
assert.ok(!isHeavyEntity({ typeId: "minecraft:pig" }));

// 2. Low-to-medium speed collision (stops truck dead, no target shove)
const lowSpeedResult = resolveHeavyCollision(0.20, { x: 1, z: 0 });
assert.equal(lowSpeedResult.truckHalted, true, "Low speed collision should halt the truck");
assert.equal(lowSpeedResult.targetShoved, false, "Golem should not be shoved at low speed");

// 3. Top-speed collision (shoves target, applies deceleration penalty, heavy damage)
const topSpeedResult = resolveHeavyCollision(0.38, { x: 1, z: 0 });
assert.equal(topSpeedResult.truckHalted, false, "Top speed collision should push through");
assert.equal(topSpeedResult.targetShoved, true, "Golem should be shoved at top speed");
assert.equal(topSpeedResult.truckDecelerated, true, "Truck should absorb deceleration penalty");
assert.ok(topSpeedResult.damage >= 50, "Top speed ramming should deal heavy damage");
assert.ok(topSpeedResult.targetImpulse.x > 0, "Target impulse should be in forward direction");
assert.ok(topSpeedResult.truckPenaltyImpulse.x < 0, "Truck penalty impulse should be backward");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
