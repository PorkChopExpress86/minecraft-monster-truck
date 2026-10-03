import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_suspension_jump_and_crush_stomp_contracts():
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")

    script = r'''
import assert from 'node:assert/strict';
import * as landing from './behavior_packs/MonsterTruck_BP/scripts/landing.js';
const { calculateCrushStompDamage, calculateShockwaveImpulse, isCrushStompLanding, CRUSH_STOMP_MIN_DROP } = landing;

// 1. The Suspension Jump is retired (ADR-0017): no jump helpers remain.
for (const name of ["calculateJumpImpulse", "canTriggerJump", "advanceJumpPhase", "JUMP_COOLDOWN_TICKS"]) {
  assert.equal(landing[name], undefined, name + " must be removed");
}

// 2. Crush Stomp needs a real drop: 3 blocks or more.
assert.equal(CRUSH_STOMP_MIN_DROP, 3);
assert.equal(isCrushStompLanding(3), true);
assert.equal(isCrushStompLanding(5.5), true);
assert.equal(isCrushStompLanding(2.9), false, "auto-step and curb drops must not crush");
assert.equal(isCrushStompLanding(0), false);

// 4. Crush Stomp landing damage
const crushDamage = calculateCrushStompDamage();
assert.ok(crushDamage >= 60, "Crush Stomp must inflict at least 60 damage");

// 5. Outward radial shockwave impulse
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


# Landing on engine ground contact, the bounded 8-tick rider reseat window, and Jump as the
# handbrake (no Suspension Jump, no playerButtonInput) are behaviour-tested in
# tests/js/truck_tick.test.mjs and tests/js/main.test.mjs.
