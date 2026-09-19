import json
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_item_texture_registration():
    it_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "textures" / "item_texture.json"
    assert it_path.exists(), "item_texture.json must exist"
    
    with open(it_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data.get("texture_name") == "atlas.items"
    tex_data = data.get("texture_data", {})
    assert "monster_truck_spawn_egg" in tex_data
    assert tex_data["monster_truck_spawn_egg"]["textures"] == "textures/items/monster_truck_spawn_egg"
    assert tex_data["monster_truck_vehicle"]["textures"] == "textures/items/monster_truck_spawn_egg"


def test_survival_vehicle_item_is_deterministically_red():
    item_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "items" / "monster_truck_vehicle.item.json"
    item = json.loads(item_path.read_text(encoding="utf-8"))["minecraft:item"]
    assert item["description"]["identifier"] == "blake:monster_truck_vehicle"
    assert item["components"]["minecraft:entity_placer"]["entity"] == (
        "blake:monster_truck<blake:spawn_red>"
    )

    recipe = json.loads(
        (REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "recipes" / "monster_truck.json")
        .read_text(encoding="utf-8")
    )["minecraft:recipe_shaped"]
    assert recipe["result"] == {"item": "blake:monster_truck_vehicle", "count": 1}

def test_client_entity_spawn_egg():
    ce_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "entity" / "monster_truck.entity.json"
    with open(ce_path, "r", encoding="utf-8") as f:
        ce_data = json.load(f)
        
    desc = ce_data["minecraft:client_entity"]["description"]
    assert "spawn_egg" not in desc, "The explicit Creative item owns randomized placement"

    item = json.loads(
        (REPO_ROOT / "behavior_packs/MonsterTruck_BP/items/monster_truck_spawn_egg.item.json")
        .read_text(encoding="utf-8")
    )["minecraft:item"]
    assert item["description"]["identifier"] == "blake:monster_truck_spawn_egg"
    assert item["components"]["minecraft:icon"]["textures"]["default"] == "monster_truck_spawn_egg"

def test_spawn_egg_and_pack_icon_assets():
    egg_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "textures" / "items" / "monster_truck_spawn_egg.png"
    bp_icon = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "pack_icon.png"
    rp_icon = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "pack_icon.png"
    
    assert egg_path.exists()
    assert bp_icon.exists()
    assert rp_icon.exists()
    
    with Image.open(egg_path) as img:
        assert img.size == (16, 16)
        assert img.mode == "RGBA"
        
    with Image.open(bp_icon) as img:
        assert img.size == (64, 64)
        
    with Image.open(rp_icon) as img:
        assert img.size == (64, 64)
