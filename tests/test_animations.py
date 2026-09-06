import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_animation_files_and_bone_parity():
    anim_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "animations" / "monster_truck.animation.json"
    geo_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "models" / "entity" / "monster_truck.geo.json"
    
    assert anim_path.exists(), "Animation JSON must exist"
    
    with open(geo_path, "r", encoding="utf-8") as f:
        geo_data = json.load(f)
    with open(anim_path, "r", encoding="utf-8") as f:
        anim_data = json.load(f)
        
    geo_bones = {b["name"] for b in geo_data["minecraft:geometry"][0]["bones"]}
    
    animations = anim_data.get("animations", {})
    assert "animation.blake.monster_truck.wheel_spin" in animations
    assert "animation.blake.monster_truck.body_bob" in animations
    
    # Assert every animated bone exists in the geometry
    for anim_name, anim in animations.items():
        for bone_name in anim.get("bones", {}).keys():
            assert bone_name in geo_bones, f"Animated bone '{bone_name}' in {anim_name} not found in geometry"

def test_animation_controller_logic():
    ac_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "animation_controllers" / "monster_truck.animation_controllers.json"
    assert ac_path.exists(), "Animation controller JSON must exist"
    
    with open(ac_path, "r", encoding="utf-8") as f:
        ac_data = json.load(f)
        
    controllers = ac_data.get("animation_controllers", {})
    assert "controller.animation.blake.monster_truck.drive" in controllers
    drive = controllers["controller.animation.blake.monster_truck.drive"]
    
    states = drive.get("states", {})
    assert "idle" in states
    assert "moving" in states
    
    # Check transitions
    idle_trans = states["idle"].get("transitions", [])
    assert any("moving" in t and "query.modified_move_speed > 0.01" in t.get("moving", "") for t in idle_trans)
    
    moving_trans = states["moving"].get("transitions", [])
    assert any("idle" in t and "query.modified_move_speed <= 0.01" in t.get("idle", "") for t in moving_trans)

def test_client_entity_animation_wiring():
    ce_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "entity" / "monster_truck.entity.json"
    with open(ce_path, "r", encoding="utf-8") as f:
        ce_data = json.load(f)
        
    desc = ce_data["minecraft:client_entity"]["description"]
    assert "animations" in desc
    assert "wheel_spin" in desc["animations"]
    assert "drive_controller" in desc["animations"]
    assert "scripts" in desc
    assert "drive_controller" in desc["scripts"].get("animate", [])
