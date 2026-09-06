import os
import json
import yaml
import pytest
from pathlib import Path

# Seam under test: project configuration and validation/packaging scripts

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_config_files_exist_and_match():
    yaml_path = REPO_ROOT / "vehicle.config.yaml"
    json_path = REPO_ROOT / "vehicle.config.json"
    
    assert yaml_path.exists(), "vehicle.config.yaml must exist"
    assert json_path.exists(), "vehicle.config.json must exist"
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
        
    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        
    assert yaml_data == json_data, "YAML and JSON config representations must match"
    
    # Required keys check
    assert yaml_data["namespace"] == "blake"
    assert yaml_data["entity_id"] == "monster_truck"
    assert yaml_data["target"]["min_engine_version"] == [1, 26, 40]
    assert yaml_data["vehicle"]["movement_speed"] == 0.40
    assert yaml_data["vehicle"]["auto_step_blocks"] == 1.0


def test_validator_detects_missing_packs(tmp_path):
    from scripts.validate_project import ProjectValidator
    
    # Run against empty directory
    validator = ProjectValidator(repo_root=tmp_path)
    errors = validator.validate_all()
    assert len(errors) > 0, "Validator must detect missing manifests and packs"


def test_packager_creates_mcaddon(tmp_path):
    from scripts.package_addon import build_addon
    
    # Setup dummy BP and RP in tmp_path
    bp_dir = tmp_path / "behavior_packs" / "MonsterTruck_BP"
    rp_dir = tmp_path / "resource_packs" / "MonsterTruck_RP"
    dist_dir = tmp_path / "dist"
    
    bp_dir.mkdir(parents=True)
    rp_dir.mkdir(parents=True)
    
    (bp_dir / "manifest.json").write_text('{"format_version": 2}', encoding="utf-8")
    (rp_dir / "manifest.json").write_text('{"format_version": 2}', encoding="utf-8")
    
    mcaddon_path = build_addon(repo_root=tmp_path, dist_dir=dist_dir)
    assert mcaddon_path.exists(), ".mcaddon archive must be created"
    assert (dist_dir / "MonsterTruck_BP.mcpack").exists(), "BP .mcpack must be created"
    assert (dist_dir / "MonsterTruck_RP.mcpack").exists(), "RP .mcpack must be created"
