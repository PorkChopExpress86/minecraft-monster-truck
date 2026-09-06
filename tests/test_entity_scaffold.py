import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_manifests_and_linking():
    bp_manifest_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    rp_manifest_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "manifest.json"
    
    assert bp_manifest_path.exists(), "BP manifest must exist"
    assert rp_manifest_path.exists(), "RP manifest must exist"
    
    with open(bp_manifest_path, "r", encoding="utf-8") as f:
        bp_manifest = json.load(f)
    with open(rp_manifest_path, "r", encoding="utf-8") as f:
        rp_manifest = json.load(f)
        
    assert bp_manifest["format_version"] == 2
    assert rp_manifest["format_version"] == 2
    assert bp_manifest["header"]["min_engine_version"] == [1, 26, 40]
    assert rp_manifest["header"]["min_engine_version"] == [1, 26, 40]
    
    rp_header_uuid = rp_manifest["header"]["uuid"]
    bp_deps = [d["uuid"] for d in bp_manifest.get("dependencies", [])]
    assert rp_header_uuid in bp_deps, "BP manifest must explicitly depend on RP header UUID"

def test_minimal_behavior_entity():
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    assert entity_path.exists(), "BP entity definition must exist"
    
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    desc = data["minecraft:entity"]["description"]
    assert desc["identifier"] == "blake:monster_truck"
    assert desc["is_spawnable"] is True
    assert desc["is_summonable"] is True

def test_client_entity_and_render_controller():
    client_entity_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "entity" / "monster_truck.entity.json"
    assert client_entity_path.exists(), "RP client entity must exist"
    
    with open(client_entity_path, "r", encoding="utf-8") as f:
        ce = json.load(f)
        
    desc = ce["minecraft:client_entity"]["description"]
    assert desc["identifier"] == "blake:monster_truck"
    assert "default" in desc["textures"]
    assert "default" in desc["geometry"]
    assert len(desc["render_controllers"]) > 0

def test_localization_exists():
    lang_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "texts" / "en_US.lang"
    assert lang_path.exists(), "en_US.lang must exist"
    content = lang_path.read_text(encoding="utf-8")
    assert "entity.blake:monster_truck.name=" in content
