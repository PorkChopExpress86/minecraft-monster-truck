import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_suspension_jump_and_crush_stomp_contracts():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  calculateJumpImpulse,
  canTriggerJump,
  calculateCrushStompDamage,
  calculateShockwaveImpulse,
  JUMP_COOLDOWN_TICKS
} from './behavior_packs/MonsterTruck_BP/scripts/suspension.js';

// 1. Cooldown cadence (1.2 seconds = 24 ticks)
assert.equal(JUMP_COOLDOWN_TICKS, 24);
assert.equal(canTriggerJump(0, 10), false, "Must not jump during cooldown");
assert.equal(canTriggerJump(0, 23), false, "Must not jump before 24 ticks");
assert.equal(canTriggerJump(0, 24), true, "Can jump once cooldown expires");
assert.equal(canTriggerJump(100, 130), true, "Can jump after cooldown");

// 2. Vertical clearance and forward momentum preservation
const heading = { x: 1, z: 0 };
const jumpImpulse = calculateJumpImpulse(0.40, heading);
assert.ok(jumpImpulse.y >= 0.80, "Vertical jump impulse must provide >= 3 blocks clearance");
assert.ok(jumpImpulse.x > 0, "Forward driving speed must be preserved in flight");

// 3. Crush Stomp landing damage
const crushDamage = calculateCrushStompDamage();
assert.ok(crushDamage >= 60, "Crush Stomp must inflict at least 60 damage");

// 4. Outward radial shockwave impulse
const truckLoc = { x: 50, y: 64, z: 50 };
const targetLoc = { x: 52, y: 64, z: 51 };
const shockwave = calculateShockwaveImpulse(targetLoc, truckLoc);
assert.ok(shockwave.x > 0, "Shockwave must push outward in +X");
assert.ok(shockwave.z > 0, "Shockwave must push outward in +Z");
assert.ok(shockwave.y > 0, "Shockwave must provide upward lift");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
