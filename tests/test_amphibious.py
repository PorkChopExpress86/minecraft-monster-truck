import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_amphibious_buoyancy_configuration():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    
    assert "minecraft:buoyant" in comps, "Entity must define minecraft:buoyant"
    buoyancy = comps["minecraft:buoyant"]
    
    # Positive buoyancy and liquid targets
    assert buoyancy["base_buoyancy"] >= 1.0, "Must have positive buoyancy"
    assert "liquid_blocks" in buoyancy
    liquids = buoyancy["liquid_blocks"]
    assert "minecraft:water" in liquids
    assert "minecraft:flowing_water" in liquids
    assert "minecraft:lava" in liquids
    assert "minecraft:flowing_lava" in liquids
    
    # Resistance to water currents
    assert comps["minecraft:knockback_resistance"]["value"] == 1.0
    
    # Seated occupants elevated above waterline
    rideable = comps["minecraft:rideable"]
    for seat in rideable["seats"]:
        assert seat["position"][1] >= 0.95, "Seat Y must be elevated above 0.8 waterline"
