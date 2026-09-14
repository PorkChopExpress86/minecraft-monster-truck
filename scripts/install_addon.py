"""Deploy the Monster Truck add-on directly to local Minecraft Bedrock installation with version revving and sync verification."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from scripts.version_manager import (
        get_repo_version,
        set_repo_version,
        bump_version,
        version_to_str,
        find_com_mojang_roots,
        sync_world_pack_versions,
        check_version_sync,
        print_status_report,
        BP_UUID,
        RP_UUID,
    )
except ImportError:
    from version_manager import (
        get_repo_version,
        set_repo_version,
        bump_version,
        version_to_str,
        find_com_mojang_roots,
        sync_world_pack_versions,
        check_version_sync,
        print_status_report,
        BP_UUID,
        RP_UUID,
    )

def install(rev=True, rev_part="patch", explicit_version=None):
    # 1. Version revving if requested
    current_ver = get_repo_version(REPO_ROOT)
    if explicit_version:
        target_ver = bump_version(repo_root=REPO_ROOT, explicit_version=explicit_version)
        print(f"[VERSION] Explicitly setting version to v{version_to_str(target_ver)}")
    elif rev:
        target_ver = bump_version(part=rev_part, repo_root=REPO_ROOT)
        print(f"[VERSION] Revving version: v{version_to_str(current_ver)} -> v{version_to_str(target_ver)} ({rev_part})")
    else:
        target_ver = current_ver
        print(f"[VERSION] Installing without version rev (v{version_to_str(target_ver)})")

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
        print(f"\nInstalling to Minecraft root: {root}")

        # 1. Global development packs
        dev_bp = root / "development_behavior_packs" / "MonsterTruck_BP"
        dev_rp = root / "development_resource_packs" / "MonsterTruck_RP"

        dev_bp.parent.mkdir(parents=True, exist_ok=True)
        dev_rp.parent.mkdir(parents=True, exist_ok=True)

        if dev_bp.exists():
            shutil.rmtree(dev_bp)
        if dev_rp.exists():
            shutil.rmtree(dev_rp)
        shutil.copytree(bp_src, dev_bp)
        shutil.copytree(rp_src, dev_rp)
        print(f"  [OK] Installed global dev behavior pack (v{version_to_str(target_ver)}): {dev_bp}")
        print(f"  [OK] Installed global dev resource pack (v{version_to_str(target_ver)}): {dev_rp}")
        deployed_count += 1

        # 2. Inspect worlds in minecraftWorlds
        worlds_dir = root / "minecraftWorlds"
        if worlds_dir.is_dir():
            for world in worlds_dir.glob("*"):
                if not world.is_dir():
                    continue

                # Check for active truck packs in world_behavior_packs.json
                wb_json = world / "world_behavior_packs.json"
                has_truck_pack = False
                if wb_json.is_file():
                    try:
                        packs = json.loads(wb_json.read_text(encoding="utf-8"))
                        if any(BP_UUID in p.get("pack_id", "") for p in packs):
                            has_truck_pack = True
                    except Exception:
                        pass

                world_name_file = world / "levelname.txt"
                wname = world_name_file.read_text(encoding="utf-8-sig").strip() if world_name_file.exists() else world.name

                # Update truck pack folders inside the world if present
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

                # Synchronize world pack versions in world_behavior_packs.json & world_resource_packs.json
                synced_manifests = sync_world_pack_versions(world, target_ver)

                if updated_world or has_truck_pack or synced_manifests:
                    print(f"  [OK] Updated active world '{wname}' ({world.name}) -> pack version v{version_to_str(target_ver)}")
                    deployed_count += 1

    # 3. Post-installation verification: verify that finished repo version and installed match!
    print("\n" + "=" * 60)
    print("POST-INSTALLATION VERSION VERIFICATION")
    print("=" * 60)
    report = check_version_sync(REPO_ROOT, mojang_roots)
    print(f"Finished Repo Version : v{report['repo_version_str']}")
    print(f"Sync Verification     : {'MATCH (IN SYNC)' if report['in_sync'] else 'MISMATCH (OUT OF SYNC)'}")
    print(f"Summary               : {report['summary']}")
    print("=" * 60)

    if not report["in_sync"]:
        print("[WARNING] One or more installed targets failed to match finished repo version.", file=sys.stderr)
        return 1

    print(f"\nSuccessfully installed Monster Truck add-on v{version_to_str(target_ver)} ({deployed_count} locations updated and verified).")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Install Monster Truck add-on with version revving and sync verification.")
    parser.add_argument("--rev", action="store_true", default=True, help="Rev patch version before installing (default)")
    parser.add_argument("--no-rev", dest="rev", action="store_false", help="Install current version without revving")
    parser.add_argument("--rev-minor", action="store_true", help="Rev minor version before installing")
    parser.add_argument("--rev-major", action="store_true", help="Rev major version before installing")
    parser.add_argument("--set-version", help="Set explicit version before installing e.g. 1.1.0")
    parser.add_argument("--check", action="store_true", help="Only verify version sync between repo and installed game")

    args = parser.parse_args()

    if args.check:
        report = print_status_report(REPO_ROOT)
        sys.exit(0 if report["in_sync"] else 1)

    part = "patch"
    if args.rev_major:
        part = "major"
    elif args.rev_minor:
        part = "minor"

    return install(rev=args.rev, rev_part=part, explicit_version=args.set_version)

if __name__ == "__main__":
    sys.exit(main())
