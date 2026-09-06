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
    assert rideable["seats"][0]["position"] == [-0.55, 1.75, 0.20]
    assert rideable["seats"][0]["third_person_camera_radius"] == 6.0
    
    # Direct ground control
    assert "minecraft:input_ground_controlled" in comps, "Entity must have minecraft:input_ground_controlled"

def test_stepping_and_movement_tuning():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    # Auto step 1.0 for monster truck obstacle traversal
    assert "minecraft:variable_max_auto_step" in comps, "Entity must have minecraft:variable_max_auto_step"
    step = comps["minecraft:variable_max_auto_step"]
    assert step["controlled_value"] == 1.0
    assert step["base_value"] == 1.0
    
    # Movement and turn rate
    assert comps["minecraft:movement"]["value"] == 0.40
    assert comps["minecraft:movement.basic"]["max_turn"] == 18.0
    
    # Friction modifier
    assert "minecraft:friction_modifier" in comps
    assert comps["minecraft:friction_modifier"]["value"] == 1.15
    
    # Behavior format version must be at least 1.26.20 for corrected friction semantics
    assert data["format_version"] >= "1.26.20"
