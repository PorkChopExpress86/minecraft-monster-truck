import os
import sys
import zipfile
from pathlib import Path

def zip_directory(source_dir: Path, output_zip: Path):
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(source_dir)
                zf.write(file_path, arcname)

def build_addon(repo_root=None, dist_dir=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    dist = Path(dist_dir) if dist_dir else (root / "dist")
    dist.mkdir(parents=True, exist_ok=True)
    
    bp_dir = root / "behavior_packs" / "MonsterTruck_BP"
    rp_dir = root / "resource_packs" / "MonsterTruck_RP"
    
    if not bp_dir.exists():
        raise FileNotFoundError(f"Behavior pack directory not found: {bp_dir}")
    if not rp_dir.exists():
        raise FileNotFoundError(f"Resource pack directory not found: {rp_dir}")
        
    bp_mcpack = dist / "MonsterTruck_BP.mcpack"
    rp_mcpack = dist / "MonsterTruck_RP.mcpack"
    mcaddon = dist / "MonsterTruck.mcaddon"
    
    print(f"Building {bp_mcpack.name}...")
    zip_directory(bp_dir, bp_mcpack)
    
    print(f"Building {rp_mcpack.name}...")
    zip_directory(rp_dir, rp_mcpack)
    
    print(f"Packaging {mcaddon.name}...")
    with zipfile.ZipFile(mcaddon, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(bp_mcpack, bp_mcpack.name)
        zf.write(rp_mcpack, rp_mcpack.name)
        
    print(f"Add-on build complete: {mcaddon}")
    return mcaddon

if __name__ == "__main__":
    build_addon()
