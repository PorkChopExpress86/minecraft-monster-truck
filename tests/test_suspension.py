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
  advanceJumpPhase,
  JUMP_COOLDOWN_TICKS,
  JUMP_VERTICAL_IMPULSE
} from './behavior_packs/MonsterTruck_BP/scripts/suspension.js';

// 1. Cooldown cadence (1.2 seconds = 24 ticks)
assert.equal(JUMP_COOLDOWN_TICKS, 24);
assert.equal(canTriggerJump(undefined, 1), true, "First jump must not require a prior timestamp");
assert.equal(canTriggerJump(0, 10), false, "Must not jump during cooldown");
assert.equal(canTriggerJump(0, 23), false, "Must not jump before 24 ticks");
assert.equal(canTriggerJump(0, 24), true, "Can jump once cooldown expires");
assert.equal(canTriggerJump(100, 130), true, "Can jump after cooldown");

// 2. Vertical clearance and forward momentum preservation
const heading = { x: 1, z: 0 };
const jumpImpulse = calculateJumpImpulse(0.40, heading);
assert.equal(JUMP_VERTICAL_IMPULSE, 1.25);
assert.equal(jumpImpulse.y, JUMP_VERTICAL_IMPULSE, "Production and helper jump height must share one authority");
assert.ok(jumpImpulse.y >= 0.80, "Vertical jump impulse must provide >= 3 blocks clearance");
assert.ok(jumpImpulse.x > 0, "Forward driving speed must be preserved in flight");

// 3. Launch, ascent, descent, and landing are distinct. Ground contact on the
// launch tick must never qualify as a landing.
let phase = advanceJumpPhase("launch", { verticalVelocity: 0, deltaY: 0, grounded: true });
assert.equal(phase.phase, "launch");
assert.equal(phase.didLand, false);
phase = advanceJumpPhase(phase.phase, { verticalVelocity: 0.7, deltaY: 0.2, grounded: false });
assert.equal(phase.phase, "ascending");
phase = advanceJumpPhase(phase.phase, { verticalVelocity: -0.2, deltaY: -0.1, grounded: false });
assert.equal(phase.phase, "descending");
phase = advanceJumpPhase(phase.phase, { verticalVelocity: 0, deltaY: 0, grounded: true });
assert.equal(phase.phase, "grounded");
assert.equal(phase.didLand, true);

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


def test_landing_uses_engine_ground_contact_instead_of_block_approximation():
    main = (REPO_ROOT / "behavior_packs/MonsterTruck_BP/scripts/main.js").read_text(encoding="utf-8")
    assert "Boolean(truck.isOnGround)" in main
    assert "blockBelowIsSolid" not in main


def test_jump_lifecycle_has_bounded_reseat_and_retrigger_guards():
    main = (REPO_ROOT / "behavior_packs/MonsterTruck_BP/scripts/main.js").read_text(encoding="utf-8")
    assert "function restoreProtectedRiders" in main
    assert "restoreProtectedRiders(state, rideable)" in main
    assert "isJumpTriggered && !state.isAirborne &&" in main
    assert "canTriggerJump(state.lastJumpTick, tickNumber)" in main
    assert "seatedDriverAssignments" in main
    assert "tick - assignment.tick <= 2" in main
    assert "state.riderRetentionUntil = tickNumber + 8" in main
    assert "system.run(() =>" in main
    assert "canTriggerJump(state.lastLandingTick, tickNumber)" in main
