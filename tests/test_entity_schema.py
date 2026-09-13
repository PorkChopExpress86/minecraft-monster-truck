import json
from pathlib import Path
import pytest

from scripts.validate_project import ProjectValidator
from scripts.bedrock_test import evaluate_lines

REPO_ROOT = Path(__file__).resolve().parent.parent

# Known valid entity component identifiers for Minecraft Bedrock vehicle/creature schemas
VALID_BEDROCK_COMPONENTS = {
    "minecraft:interact",
    "minecraft:type_family",
    "minecraft:health",
    "minecraft:collision_box",
    "minecraft:physics",
    "minecraft:movement",
    "minecraft:movement.basic",
    "minecraft:navigation.walk",
    "minecraft:rideable",
    "minecraft:input_ground_controlled",
    "minecraft:variable_max_auto_step",
    "minecraft:friction_modifier",
    "minecraft:knockback_resistance",
    "minecraft:buoyant",
    "minecraft:nameable",
    "minecraft:loot",
    "minecraft:damage_sensor",
    "minecraft:area_attack",
}


def test_entity_has_no_invalid_buoyancy_component():
    """Ensure the entity definition does not use the rejected 'minecraft:buoyancy' component."""
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    content = entity_path.read_text(encoding="utf-8")
    
    # Must not contain minecraft:buoyancy anywhere
    assert "minecraft:buoyancy" not in content, (
        "Entity must not contain 'minecraft:buoyancy'; Bedrock 1.26 requires 'minecraft:buoyant'"
    )
    
    data = json.loads(content)
    comps = data["minecraft:entity"]["components"]
    assert "minecraft:buoyant" in comps, "Entity must define 'minecraft:buoyant'"
    assert "minecraft:buoyancy" not in comps


def test_buoyant_component_schema_conformance():
    """Verify that minecraft:buoyant uses valid Bedrock 1.26 schema properties."""
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    buoyant = data["minecraft:entity"]["components"]["minecraft:buoyant"]
    assert isinstance(buoyant, dict)
    
    # Required/allowed schema fields
    assert buoyant.get("apply_gravity") is True
    assert buoyant.get("base_buoyancy", 0) >= 1.0
    assert "liquid_blocks" in buoyant
    assert isinstance(buoyant["liquid_blocks"], list)
    
    # Disallow deprecated or invalid properties that cause Bedrock schema parse errors
    assert "simulate_waves" not in buoyant, "simulate_waves is obsolete in 1.26; use movement_type"
    assert "water_movement_factor" not in buoyant, "water_movement_factor is not in Bedrock schema"
    assert buoyant.get("movement_type") in ("none", "waves", "player_controlled")
    
    # Verify water and lava liquids
    liquids = buoyant["liquid_blocks"]
    for expected in ("minecraft:water", "minecraft:flowing_water", "minecraft:lava", "minecraft:flowing_lava"):
        assert expected in liquids, f"liquid_blocks must include {expected}"


def test_all_entity_components_are_valid_bedrock_components():
    """Verify that every declared component is in the recognized Bedrock schema."""
    entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    with open(entity_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    comps = data["minecraft:entity"]["components"]
    for comp_name in comps.keys():
        assert comp_name.startswith("minecraft:"), f"Component '{comp_name}' must start with 'minecraft:'"
        assert comp_name in VALID_BEDROCK_COMPONENTS, (
            f"Component '{comp_name}' is not in known valid Bedrock components: {VALID_BEDROCK_COMPONENTS}"
        )


def test_validator_catches_invalid_buoyancy_component(tmp_path):
    """ProjectValidator must reject an entity containing 'minecraft:buoyancy'."""
    bp_dir = tmp_path / "behavior_packs" / "MonsterTruck_BP" / "entities"
    bp_dir.mkdir(parents=True)
    
    bad_entity = {
        "format_version": "1.26.20",
        "minecraft:entity": {
            "description": {"identifier": "blake:monster_truck"},
            "components": {
                "minecraft:buoyancy": {"base_buoyancy": 1.0}
            }
        }
    }
    (bp_dir / "monster_truck.entity.json").write_text(json.dumps(bad_entity), encoding="utf-8")
    
    validator = ProjectValidator(repo_root=tmp_path)
    config = {"namespace": "blake", "entity_id": "monster_truck"}
    validator.validate_entities(config)
    
    assert any("minecraft:buoyancy" in err for err in validator.errors), (
        "ProjectValidator must log an error when 'minecraft:buoyancy' is present"
    )


def test_validator_catches_unsupported_buoyant_properties(tmp_path):
    """ProjectValidator must reject obsolete or unsupported buoyant properties."""
    bp_dir = tmp_path / "behavior_packs" / "MonsterTruck_BP" / "entities"
    bp_dir.mkdir(parents=True)
    
    bad_entity = {
        "format_version": "1.26.20",
        "minecraft:entity": {
            "description": {"identifier": "blake:monster_truck"},
            "components": {
                "minecraft:buoyant": {
                    "liquid_blocks": ["minecraft:water"],
                    "simulate_waves": True,
                    "water_movement_factor": 0.70
                }
            }
        }
    }
    (bp_dir / "monster_truck.entity.json").write_text(json.dumps(bad_entity), encoding="utf-8")
    
    validator = ProjectValidator(repo_root=tmp_path)
    config = {"namespace": "blake", "entity_id": "monster_truck"}
    validator.validate_entities(config)
    
    assert any("simulate_waves" in err for err in validator.errors)
    assert any("water_movement_factor" in err for err in validator.errors)


def test_in_game_runner_flags_bedrock_schema_errors():
    """bedrock_test.evaluate_lines must flag Bedrock schema parse errors from content log."""
    log_lines = [
        ("content.log", "14:13:17[Log][error]-Monster Truck | actor_definitions | blake:monster_truck | -> components -> minecraft:buoyancy: this component was found in the input, but is not present in the Schema"),
        ("content.log", "14:13:17[Actor][error]-Monster Truck | actor_definitions | ERROR: Entity 'blake:monster_truck' failed to load from JSON: parse errors occurred"),
        ("content.log", "14:13:22[Recipes][error]-recipes/monster_truck.json | The Item: blake:monster_truck_spawn_egg is missing or invalid, can't make the recipe"),
    ]
    
    errors, warnings, markers = evaluate_lines(log_lines, "test-run", "blake:monster_truck")
    
    assert len(errors) == 3, f"All 3 schema/recipe errors must be captured, got {errors}"
    assert any("buoyancy" in err for err in errors)
    assert any("failed to load from JSON" in err for err in errors)
    assert any("missing or invalid" in err for err in errors)
