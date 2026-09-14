import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_rideable_and_control_components():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    # Rideable
    assert "minecraft:rideable" in comps, "Entity must have minecraft:rideable"
    rideable = comps["minecraft:rideable"]
    assert rideable["seat_count"] == 2
    assert rideable["controlling_seat"] == 0
    assert "player" in rideable["family_types"]
    assert isinstance(rideable["seats"], list), "seats must be a list of seat objects"
    assert rideable["seats"][0]["position"] == [0.45, 1.15, 0.15]
    assert rideable["seats"][0]["third_person_camera_radius"] == 7.5
    assert rideable["seats"][1]["position"] == [-0.45, 1.15, 0.15]
    assert rideable["seats"][1]["third_person_camera_radius"] == 7.5
    
    # Ground WASD driving authority and native suspension jump
    assert "minecraft:input_ground_controlled" in comps, "Entity must use input_ground_controlled for responsive WASD driving"
    assert "minecraft:can_power_jump" in comps, "Entity must have minecraft:can_power_jump"
    assert comps["minecraft:horse.jump_strength"]["value"] == 0.85, "Jump strength must be tuned to 0.85 for 3-block clearance"
    assert "minecraft:is_tamed" in comps, "Entity must be pre-tamed for instant driving"
    assert "minecraft:is_saddled" in comps, "Entity must be pre-saddled for jump authority"

def test_stepping_and_movement_tuning():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    # Auto step 2.0 for monster truck obstacle traversal
    assert "minecraft:variable_max_auto_step" in comps, "Entity must have minecraft:variable_max_auto_step"
    step = comps["minecraft:variable_max_auto_step"]
    assert step["controlled_value"] == 2.0
    assert step["base_value"] == 2.0
    
    # Movement and turn rate
    assert comps["minecraft:movement"]["value"] == 0.55
    assert comps["minecraft:movement.basic"]["max_turn"] == 18.0
    
    # Friction modifier
    assert "minecraft:friction_modifier" in comps
    assert comps["minecraft:friction_modifier"]["value"] == 1.15
    
    # Behavior format version must be at least 1.26.20 for corrected friction semantics
    assert data["format_version"] >= "1.26.20"

def test_canopy_clearance_collision_profile():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    comps = data["minecraft:entity"]["components"]
    
    collision = comps["minecraft:collision_box"]
    assert collision["height"] <= 1.95, "Collision box height must be <= 1.95 blocks to clear 2.0-block tree canopies"
    assert collision["width"] == 2.25

