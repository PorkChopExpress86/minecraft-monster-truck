import os
import sys
import json
import yaml
from pathlib import Path

class ProjectValidator:
    def __init__(self, repo_root=None):
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
        self.errors = []
        self.warnings = []
        
    def log_error(self, message):
        self.errors.append(message)
        
    def log_warning(self, message):
        self.warnings.append(message)
        
    def load_json(self, path):
        if not path.exists():
            self.log_error(f"File not found: {path.relative_to(self.repo_root) if path.is_relative_to(self.repo_root) else path}")
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.log_error(f"Failed to parse JSON in {path}: {e}")
            return None

    def validate_config(self):
        cfg_yaml = self.repo_root / "vehicle.config.yaml"
        cfg_json = self.repo_root / "vehicle.config.json"
        
        if not cfg_yaml.exists() and not cfg_json.exists():
            self.log_error("Neither vehicle.config.yaml nor vehicle.config.json exists.")
            return None
            
        config = None
        if cfg_yaml.exists():
            try:
                with open(cfg_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
            except Exception as e:
                self.log_error(f"Error parsing vehicle.config.yaml: {e}")
        elif cfg_json.exists():
            config = self.load_json(cfg_json)
            
        if config:
            for req in ["namespace", "entity_id", "display_name", "target", "vehicle"]:
                if req not in config:
                    self.log_error(f"Missing required config key: {req}")
        return config

    def validate_manifests(self):
        bp_manifest_path = self.repo_root / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
        rp_manifest_path = self.repo_root / "resource_packs" / "MonsterTruck_RP" / "manifest.json"
        
        bp_manifest = self.load_json(bp_manifest_path)
        rp_manifest = self.load_json(rp_manifest_path)
        
        if not bp_manifest or not rp_manifest:
            return
            
        # Manifest format check
        if bp_manifest.get("format_version") != 2:
            self.log_error(f"BP manifest format_version must be 2, got {bp_manifest.get('format_version')}")
        if rp_manifest.get("format_version") != 2:
            self.log_error(f"RP manifest format_version must be 2, got {rp_manifest.get('format_version')}")
            
        # RP header UUID check
        rp_header_uuid = rp_manifest.get("header", {}).get("uuid")
        if not rp_header_uuid:
            self.log_error("RP manifest missing header UUID")
            
        # Check BP dependencies point to RP header UUID
        bp_deps = bp_manifest.get("dependencies", [])
        found_rp_dep = False
        for dep in bp_deps:
            if dep.get("uuid") == rp_header_uuid:
                found_rp_dep = True
                break
        if not found_rp_dep:
            self.log_error(f"BP manifest dependencies does not contain RP header UUID ({rp_header_uuid})")

    def validate_entities(self, config):
        if not config:
            return
        identifier = f"{config['namespace']}:{config['entity_id']}"
        
        bp_entity_path = self.repo_root / "behavior_packs" / "MonsterTruck_BP" / "entities" / f"{config['entity_id']}.entity.json"
        rp_entity_path = self.repo_root / "resource_packs" / "MonsterTruck_RP" / "entity" / f"{config['entity_id']}.entity.json"
        
        bp_entity = self.load_json(bp_entity_path)
        rp_entity = self.load_json(rp_entity_path)
        
        if bp_entity:
            desc = bp_entity.get("minecraft:entity", {}).get("description", {})
            if desc.get("identifier") != identifier:
                self.log_error(f"BP entity identifier mismatch: expected {identifier}, got {desc.get('identifier')}")
                
        if rp_entity:
            desc = rp_entity.get("minecraft:client_entity", {}).get("description", {})
            if desc.get("identifier") != identifier:
                self.log_error(f"RP client entity identifier mismatch: expected {identifier}, got {desc.get('identifier')}")

    def validate_images(self):
        try:
            from PIL import Image
        except ImportError:
            self.log_warning("Pillow not installed; skipping image dimension verification")
            return
            
        image_expectations = [
            (self.repo_root / "resource_packs" / "MonsterTruck_RP" / "textures" / "entity" / "monster_truck.png", (256, 256)),
            (self.repo_root / "resource_packs" / "MonsterTruck_RP" / "textures" / "items" / "monster_truck_spawn_egg.png", (16, 16)),
            (self.repo_root / "behavior_packs" / "MonsterTruck_BP" / "pack_icon.png", (64, 64)),
            (self.repo_root / "resource_packs" / "MonsterTruck_RP" / "pack_icon.png", (64, 64)),
        ]
        
        for path, expected_size in image_expectations:
            if path.exists():
                try:
                    with Image.open(path) as img:
                        if img.size != expected_size:
                            self.log_error(f"Image {path.name} dimension mismatch: expected {expected_size}, got {img.size}")
                except Exception as e:
                    self.log_error(f"Failed to inspect image {path}: {e}")

    def validate_all(self):
        self.errors.clear()
        self.warnings.clear()
        
        config = self.validate_config()
        self.validate_manifests()
        self.validate_entities(config)
        self.validate_images()
        
        return self.errors

def main():
    validator = ProjectValidator()
    errors = validator.validate_all()
    
    if validator.warnings:
        for w in validator.warnings:
            print(f"[WARN] {w}")
            
    if errors:
        print("Validation FAILED:")
        for err in errors:
            print(f"  - [ERROR] {err}")
        sys.exit(1)
    else:
        print("All validations PASSED successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
