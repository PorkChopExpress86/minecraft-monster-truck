"""Deploy the Monster Truck add-on directly to local Minecraft Bedrock installation."""
import json
import os
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

def find_com_mojang_roots():
    roots = []
    # 1. GDK Roaming path
    roaming_users = Path(os.environ.get("APPDATA", "")) / "Minecraft Bedrock/Users"
    if roaming_users.is_dir():
        for user_dir in roaming_users.glob("*/games/com.mojang"):
            if user_dir.parent.name != "Shared":
                roots.append(user_dir.resolve())
    
    # 2. Legacy UWP LocalAppData path
    legacy = (Path(os.environ.get("LOCALAPPDATA", "")) /
              "Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang")
    if legacy.is_dir() and legacy.resolve() not in roots:
        roots.append(legacy.resolve())
        
    return roots

def install():
    bp_src = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP"
    rp_src = REPO_ROOT / "resource_packs" / "MonsterTruck_RP"
    
    if not bp_src.is_dir() or not rp_src.is_dir():
        print(f"[ERROR] Source packs missing in {REPO_ROOT}", file=sys.stderr)
        return 1

    mojang_roots = find_com_mojang_roots()
    if not mojang_roots:
        print("[ERROR] No local Minecraft Bedrock installation found.", file=sys.stderr)
        return 1

    deployed_count = 0
    for root in mojang_roots:
        print(f"Installing to Minecraft root: {root}")
        
        # 1. Global development packs
        dev_bp = root / "development_behavior_packs" / "MonsterTruck_BP"
        dev_rp = root / "development_resource_packs" / "MonsterTruck_RP"
        
        dev_bp.parent.mkdir(parents=True, exist_ok=True)
        dev_rp.parent.mkdir(parents=True, exist_ok=True)
        
        if dev_bp.exists(): shutil.rmtree(dev_bp)
        if dev_rp.exists(): shutil.rmtree(dev_rp)
        shutil.copytree(bp_src, dev_bp)
        shutil.copytree(rp_src, dev_rp)
        print(f"  [OK] Installed global dev behavior pack: {dev_bp}")
        print(f"  [OK] Installed global dev resource pack: {dev_rp}")
        deployed_count += 1
        
        # 2. Inspect worlds in minecraftWorlds
        worlds_dir = root / "minecraftWorlds"
        if worlds_dir.is_dir():
            for world in worlds_dir.glob("*"):
                if not world.is_dir():
                    continue
                
                # Check for active truck packs
                wb_json = world / "world_behavior_packs.json"
                has_truck_pack = False
                if wb_json.is_file():
                    try:
                        packs = json.loads(wb_json.read_text(encoding="utf-8"))
                        if any("bc617e1c-0c92-4f91-ab9b-241d7ef141d0" in p.get("pack_id", "") for p in packs):
                            has_truck_pack = True
                    except Exception:
                        pass
                
                world_name_file = world / "levelname.txt"
                wname = world_name_file.read_text(encoding="utf-8-sig").strip() if world_name_file.exists() else world.name
                
                # Update truck pack folders inside the world
                w_bp = world / "behavior_packs"
                w_rp = world / "resource_packs"
                
                updated_world = False
                if w_bp.is_dir():
                    for bp_folder in w_bp.glob("*"):
                        if (bp_folder / "entities/monster_truck.entity.json").exists() or "MonsterTru" in bp_folder.name:
                            shutil.rmtree(bp_folder)
                            shutil.copytree(bp_src, bp_folder)
                            updated_world = True
                            
                if w_rp.is_dir():
                    for rp_folder in w_rp.glob("*"):
                        if (rp_folder / "entity/monster_truck.entity.json").exists() or "MonsterTru" in rp_folder.name:
                            shutil.rmtree(rp_folder)
                            shutil.copytree(rp_src, rp_folder)
                            updated_world = True
                            
                if updated_world or has_truck_pack:
                    print(f"  [OK] Updated active world '{wname}' ({world.name})")
                    deployed_count += 1

    print(f"\nSuccessfully installed Monster Truck add-on ({deployed_count} locations updated).")
    return 0

if __name__ == "__main__":
    sys.exit(install())
