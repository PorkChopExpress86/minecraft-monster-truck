import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_trample_files_exist():
    trample_script = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "trample.js"
    assert trample_script.exists(), "trample.js must exist"

def test_trample_math_and_protection_contracts():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  calculateTrampleDamage,
  canApplyTireTrample,
  isInContactPerimeter,
  calculateKnockbackImpulse,
  isProtectedTarget
} from './behavior_packs/MonsterTruck_BP/scripts/trample.js';

// 1. Damage scaling tests
// Parked / idling (speed 0): 0 damage
assert.equal(calculateTrampleDamage(0), 0);
// Low-speed crawling (speed 0.05): 0 damage (mobs unharmed)
assert.equal(calculateTrampleDamage(0.05), 0);
assert.equal(canApplyTireTrample(0.50, true), false, "Airborne tires cannot trample targets");
assert.equal(canApplyTireTrample(0.50, false), true, "Grounded moving tires can trample targets");
// Medium speed (0.15): minor/moderate damage (18 damage)
assert.equal(calculateTrampleDamage(0.15), 18);
// Ramming speed (0.35): heavy crushing damage (42 damage)
assert.ok(calculateTrampleDamage(0.35) >= 40);
// Top speed (0.50): lethal crushing damage (60 damage)
assert.ok(calculateTrampleDamage(0.50) >= 60);

// 2. Contact perimeter coverage (1.6 blocks around perimeter)
const truckLoc = { x: 10, y: 64, z: 10 };
const heading = { x: 1, z: 0 }; // Facing +X

// Target right beside the truck wheel (lateral offset 1.5 blocks from center, truck half-width ~1.1)
assert.ok(isInContactPerimeter({ x: 10, y: 64, z: 12.0 }, truckLoc, heading));
// Target 1.5 blocks in front of front bumper
assert.ok(isInContactPerimeter({ x: 13.0, y: 64, z: 10 }, truckLoc, heading));
// Target far away (10 blocks away)
assert.ok(!isInContactPerimeter({ x: 25, y: 64, z: 10 }, truckLoc, heading));

// 3. Outward knockback impulse
const knockback = calculateKnockbackImpulse({ x: 12, y: 64, z: 11 }, truckLoc, 0.4);
assert.ok(knockback.x > 0, "Knockback should be outward (+X)");
assert.ok(knockback.z > 0, "Knockback should be outward (+Z)");
assert.ok(knockback.y > 0, "Knockback should have upward lift");

// 4. Target protection checks
// Player protected
assert.ok(isProtectedTarget({ typeId: "minecraft:player" }, { id: "truck1" }));
// Tamed pet protected
assert.ok(isProtectedTarget({ typeId: "minecraft:wolf", isTamed: true }, { id: "truck1" }));
// Truck itself protected
assert.ok(isProtectedTarget({ id: "truck1", typeId: "blake:monster_truck" }, { id: "truck1" }));
// Hostile mob not protected
assert.ok(!isProtectedTarget({ typeId: "minecraft:zombie", isTamed: false }, { id: "truck1" }));
// Untamed animal not protected
assert.ok(!isProtectedTarget({ typeId: "minecraft:pig", isTamed: false }, { id: "truck1" }));
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
