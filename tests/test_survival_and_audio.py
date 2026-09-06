import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_two_seat_configuration():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    rideable = comps["minecraft:rideable"]
    
    assert rideable["seat_count"] == 2, "Must have 2 seats (Driver + Passenger)"
    assert rideable["controlling_seat"] == 0, "Seat 0 must be the controlling seat"
    assert len(rideable["seats"]) == 2
    
    driver_seat = rideable["seats"][0]
    passenger_seat = rideable["seats"][1]
    
    assert driver_seat["position"] == [-0.55, 1.75, 0.20], "Driver seat must be on the left"
    assert passenger_seat["position"] == [0.55, 1.75, 0.20], "Passenger seat must be on the right"

def test_durability_and_loot():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    assert comps["minecraft:health"]["value"] == 250, "Health must be 250 HP"
    assert comps["minecraft:health"]["max"] == 250
    
    loot_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "loot_tables" / "entities" / "monster_truck.json"
    assert loot_path.exists(), "Loot table for monster truck must exist"
    with open(loot_path, "r", encoding="utf-8") as f:
        loot = json.load(f)
    assert "pools" in loot

def test_crafting_recipe():
    recipe_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "recipes" / "monster_truck.json"
    assert recipe_path.exists(), "Survival crafting recipe must exist"
    
    with open(recipe_path, "r", encoding="utf-8") as f:
        recipe = json.load(f)
        
    shaped = recipe["minecraft:recipe_shaped"]
    pattern = shaped["pattern"]
    assert len(pattern) == 3
    key = shaped["key"]
    
    # Check key components
    assert "I" in key and key["I"]["item"] == "minecraft:iron_block"
    assert "G" in key and key["G"]["item"] == "minecraft:glass"
    assert "B" in key and key["B"]["item"] == "minecraft:iron_ingot"
    assert "F" in key and key["F"]["item"] == "minecraft:blast_furnace"
    assert "S" in key and key["S"]["item"] == "minecraft:saddle"
    assert "C" in key and key["C"]["item"] == "minecraft:coal_block"
    assert "R" in key and key["R"]["item"] == "minecraft:redstone_block"

def test_audio_pipeline_and_timeline():
    rp_sounds = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "sounds"
    idle_ogg = rp_sounds / "monster_truck" / "engine_idle.ogg"
    drive_ogg = rp_sounds / "monster_truck" / "engine_drive.ogg"
    
    assert idle_ogg.exists(), "engine_idle.ogg must exist"
    assert drive_ogg.exists(), "engine_drive.ogg must exist"
    assert idle_ogg.stat().st_size > 0
    assert drive_ogg.stat().st_size > 0
    
    sound_def_path = rp_sounds / "sound_definitions.json"
    assert sound_def_path.exists(), "sound_definitions.json must exist"
    with open(sound_def_path, "r", encoding="utf-8") as f:
        sound_defs = json.load(f)
    assert "blake.monster_truck.idle" in sound_defs["sound_definitions"]
    assert "blake.monster_truck.drive" in sound_defs["sound_definitions"]
    
    anim_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "animations" / "monster_truck.animation.json"
    with open(anim_path, "r", encoding="utf-8") as f:
        anims = json.load(f)["animations"]
    assert "sound_effects" in anims["animation.blake.monster_truck.wheel_spin"]
