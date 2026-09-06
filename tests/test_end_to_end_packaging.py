import zipfile
from pathlib import Path
from scripts.package_addon import build_addon

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_full_project_packaging_and_archives():
    dist_dir = REPO_ROOT / "dist"
    addon_path = build_addon(repo_root=REPO_ROOT, dist_dir=dist_dir)
    
    assert addon_path.exists()
    assert addon_path.name == "MonsterTruck.mcaddon"
    
    bp_pack = dist_dir / "MonsterTruck_BP.mcpack"
    rp_pack = dist_dir / "MonsterTruck_RP.mcpack"
    
    assert bp_pack.exists()
    assert rp_pack.exists()
    
    # Inspect BP archive root
    with zipfile.ZipFile(bp_pack, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist, "BP mcpack must have manifest.json at archive root"
        assert "entities/monster_truck.entity.json" in namelist or "entities\\monster_truck.entity.json" in namelist
        
    # Inspect RP archive root
    with zipfile.ZipFile(rp_pack, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist, "RP mcpack must have manifest.json at archive root"
        assert "textures/item_texture.json" in [n.replace("\\", "/") for n in namelist]
        
    # Inspect .mcaddon archive contents
    with zipfile.ZipFile(addon_path, "r") as zf:
        namelist = zf.namelist()
        assert "MonsterTruck_BP.mcpack" in namelist
        assert "MonsterTruck_RP.mcpack" in namelist

def test_proving_ground_documentation_exists():
    doc_path = REPO_ROOT / "docs" / "PROVING_GROUND.md"
    assert doc_path.exists(), "docs/PROVING_GROUND.md must exist"
    
    content = doc_path.read_text(encoding="utf-8")
    assert "/summon blake:monster_truck" in content
    assert "auto_step" in content.lower() or "auto-step" in content.lower()
    assert "content log" in content.lower()
