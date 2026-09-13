import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_airborne_demolition_and_crush_logic_contracts():
    main_script = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js"
    assert main_script.exists()
    content = main_script.read_text(encoding="utf-8")
    
    # Check airborne demolition bypass
    assert "state.isAirborne" in content, "Must track airborne state for jump trajectory"
    assert "calculateCrushStompDamage" in content
    assert "calculateShockwaveImpulse" in content
    assert "isProtectedTarget" in content

def test_crush_stomp_protections_and_damage_via_node():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  calculateCrushStompDamage,
  calculateShockwaveImpulse
} from './behavior_packs/MonsterTruck_BP/scripts/suspension.js';
import { isProtectedTarget } from './behavior_packs/MonsterTruck_BP/scripts/trample.js';

// 1. Crush Stomp damage >= 60
const damage = calculateCrushStompDamage();
assert.ok(damage >= 60, `Crush damage must be at least 60, got ${damage}`);

// 2. Protections: players and tamed companions spared
assert.ok(isProtectedTarget({ typeId: "minecraft:player" }, { id: "truck1" }));
assert.ok(isProtectedTarget({ typeId: "minecraft:wolf", isTamed: true }, { id: "truck1" }));
assert.ok(!isProtectedTarget({ typeId: "minecraft:zombie", isTamed: false }, { id: "truck1" }));
assert.ok(!isProtectedTarget({ typeId: "minecraft:creeper", isTamed: false }, { id: "truck1" }));

// 3. Radial shockwave impulse
const truckPos = { x: 0, y: 64, z: 0 };
const mobPos = { x: 2, y: 64, z: 2 };
const impulse = calculateShockwaveImpulse(mobPos, truckPos, 1.5);
assert.ok(impulse.x > 0, "Impulse X must be outward");
assert.ok(impulse.z > 0, "Impulse Z must be outward");
assert.ok(impulse.y > 0, "Impulse Y must have upward shockwave lift");
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
