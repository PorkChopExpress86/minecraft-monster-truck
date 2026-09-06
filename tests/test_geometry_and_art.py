import json
from pathlib import Path
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_geometry_structure_and_wheel_bones():
    geo_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "models" / "entity" / "monster_truck.geo.json"
    assert geo_path.exists(), "Geometry JSON must exist"
    
    with open(geo_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    geom = data["minecraft:geometry"][0]
    bone_names = {bone["name"] for bone in geom["bones"]}
    
    expected_bones = {"root", "body", "wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr", "roll_cage"}
    assert expected_bones.issubset(bone_names), f"Missing expected bones: {expected_bones - bone_names}"
    
    # Assert wheel bones have pivots centered on wheels
    bone_dict = {b["name"]: b for b in geom["bones"]}
    for wheel in ["wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"]:
        assert "pivot" in bone_dict[wheel], f"{wheel} must declare a pivot for rotational animation"
        assert len(bone_dict[wheel].get("cubes", [])) > 0, f"{wheel} must have cube definition"

def test_art_documentation_and_texture_atlas():
    uv_spec = REPO_ROOT / "sources" / "texture_uv_spec.md"
    bb_handoff = REPO_ROOT / "sources" / "BLOCKBENCH_HANDOFF.md"
    
    assert uv_spec.exists(), "sources/texture_uv_spec.md must exist"
    assert bb_handoff.exists(), "sources/BLOCKBENCH_HANDOFF.md must exist"
    
    tex_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "textures" / "entity" / "monster_truck.png"
    assert tex_path.exists()
    with Image.open(tex_path) as img:
        assert img.size == (256, 256)
        assert img.mode == "RGBA"
