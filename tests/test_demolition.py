import json
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_manifest_script_module_and_server_dependency():
    manifest_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    assert manifest_path.exists()
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    modules = manifest.get("modules", [])
    script_modules = [m for m in modules if m.get("type") == "script"]
    assert len(script_modules) == 1, "Must have exactly 1 script module"
    assert script_modules[0]["entry"] == "scripts/main.js"
    
    dependencies = manifest.get("dependencies", [])
    server_deps = [d for d in dependencies if d.get("module_name") == "@minecraft/server"]
    assert len(server_deps) == 1, "Must declare @minecraft/server dependency"
    assert server_deps[0]["version"] == "2.0.0"

def test_script_entry_point_exists_and_valid():
    entry_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js"
    assert entry_path.exists(), "scripts/main.js must exist"
    
    node_exe = shutil.which("node")
    if node_exe:
        # Check syntax using node --check
        res = subprocess.run([node_exe, "--check", str(entry_path)], capture_output=True, text=True)
        assert res.returncode == 0, f"Script syntax error: {res.stderr}"

def test_demolition_logic_contracts():
    entry_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "main.js"
    demo_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "scripts" / "demolition.js"
    main_content = entry_path.read_text(encoding="utf-8")
    demo_content = demo_path.read_text(encoding="utf-8")
    
    # Threshold check
    assert "0.25" in main_content, "Momentum threshold of 0.25 blocks/tick must be present"
    assert "air destroy" in main_content, "Must use air destroy to break blocks with survival drops"
    
    # Foliage and wood filtering keywords
    assert "leaves" in demo_content.lower()
    assert "log" in demo_content.lower()
    assert "planks" in demo_content.lower()
    assert "glass" in demo_content.lower()

def test_demolition_helpers_via_node():
    node_exe = shutil.which("node")
    if not node_exe:
        return
    
    script = r'''
import assert from 'node:assert/strict';
import { isFoliage, isDestructibleWoodOrGlass } from './behavior_packs/MonsterTruck_BP/scripts/demolition.js';

// Foliage checks
assert.ok(isFoliage("minecraft:oak_leaves"));
assert.ok(isFoliage("minecraft:azalea_leaves"));
assert.ok(isFoliage("minecraft:vine"));
assert.ok(isFoliage("minecraft:tall_grass"));
assert.ok(isFoliage("minecraft:fern"));
assert.ok(!isFoliage("minecraft:oak_planks"));
assert.ok(!isFoliage("minecraft:stone"));

// Destructible wood & glass checks
assert.ok(isDestructibleWoodOrGlass("minecraft:oak_log"));
assert.ok(isDestructibleWoodOrGlass("minecraft:oak_planks"));
assert.ok(isDestructibleWoodOrGlass("minecraft:birch_fence"));
assert.ok(isDestructibleWoodOrGlass("minecraft:oak_door"));
assert.ok(isDestructibleWoodOrGlass("minecraft:spruce_stairs"));
assert.ok(isDestructibleWoodOrGlass("minecraft:glass"));
assert.ok(isDestructibleWoodOrGlass("minecraft:stained_glass_pane"));

// Indestructible / hard material exclusions
assert.ok(!isDestructibleWoodOrGlass("minecraft:stone"));
assert.ok(!isDestructibleWoodOrGlass("minecraft:iron_block"));
assert.ok(!isDestructibleWoodOrGlass("minecraft:cobblestone"));
assert.ok(!isDestructibleWoodOrGlass("minecraft:obsidian"));
assert.ok(!isDestructibleWoodOrGlass("minecraft:dirt"));
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

