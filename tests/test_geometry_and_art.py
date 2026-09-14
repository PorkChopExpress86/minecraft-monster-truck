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
    
    expected_bones = {"root", "body", "wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr", "roll_cage", "steer_fl", "steer_fr", "steer_rl", "steer_rr"}
    assert expected_bones.issubset(bone_names), f"Missing expected bones: {expected_bones - bone_names}"
    
    bone_dict = {b["name"]: b for b in geom["bones"]}
    # Assert steering knuckle bones parent the wheel bones with matching pivots
    for corner in ["fl", "fr", "rl", "rr"]:
        steer_bone = f"steer_{corner}"
        wheel_bone = f"wheel_{corner}"
        assert steer_bone in bone_dict, f"{steer_bone} must exist in geometry"
        assert bone_dict[steer_bone].get("parent") == "root", f"{steer_bone} must be parented to root"
        assert bone_dict[wheel_bone].get("parent") == steer_bone, f"{wheel_bone} must be parented to {steer_bone}"
        assert bone_dict[steer_bone].get("pivot") == bone_dict[wheel_bone].get("pivot"), f"{steer_bone} pivot must match {wheel_bone} pivot"
        assert len(bone_dict[wheel_bone].get("cubes", [])) > 0, f"{wheel_bone} must have cube definition"

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

def test_cab_geometry_sightlines_and_transparency():
    """Verify sloped hood, elevated roof, and crystal clear windshield transparency."""
    geo_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "models" / "entity" / "monster_truck.geo.json"
    with open(geo_path, "r", encoding="utf-8") as f:
        geom = json.load(f)["minecraft:geometry"][0]
    
    body_bone = next(b for b in geom["bones"] if b["name"] == "body")
    cubes = body_bone["cubes"]
    
    # Windshield cube exists and spans Y >= 34 to 44
    windshields = [c for c in cubes if c.get("origin", [0,0,0])[2] == -8.5]
    assert len(windshields) == 1, "Windshield cube must exist at Z=-8.5"
    assert windshields[0]["size"][1] >= 9, "Windshield height must be at least 9 units for clear sightline"
    
    # Roof is elevated to Y >= 44
    roofs = [c for c in cubes if c.get("origin", [0,0,0])[1] >= 44 and c.get("size", [0,0,0])[0] >= 28]
    assert len(roofs) >= 1, "Roof must be elevated to Y>=44 for head clearance"
    
    # Texture at glass swatch (20, 80) is 100% transparent (alpha == 0)
    tex_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "textures" / "entity" / "monster_truck.png"
    with Image.open(tex_path) as img:
        pixel = img.getpixel((20, 80))
        assert pixel[3] == 0, f"Glass swatch alpha must be 0 (100% transparent), got {pixel[3]}"
