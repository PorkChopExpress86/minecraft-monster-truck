"""Deploy the Monster Truck add-on directly to local Minecraft Bedrock installation with version revving and sync verification."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from scripts.addon_packs import AddonPacks, com_mojang_roots, read_json
    from scripts.version_manager import (
        get_repo_version,
        set_repo_version,
        bump_version,
        version_to_str,
        sync_world_pack_versions,
        check_version_sync,
        print_status_report,
    )
except ImportError:
    from addon_packs import AddonPacks, com_mojang_roots, read_json
    from version_manager import (
        get_repo_version,
        set_repo_version,
        bump_version,
        version_to_str,
        sync_world_pack_versions,
        check_version_sync,
        print_status_report,
    )

# Opt-in Docker Bedrock Dedicated Server targets (itzg/minecraft-bedrock-server containers).
SERVER_CONTAINERS = {"creative": "minecraft-creative", "survival": "minecraft-survival"}


def docker(*args, input=None):
    return subprocess.run(["docker", *args], input=input, capture_output=True, text=True)


def install_to_server(name, version, packs, run=docker, confirm=input):
    """Deploy both packs into a server container, activate them in its world, then confirm a restart."""
    container = SERVER_CONTAINERS[name]

    def check(result, action):
        if result.returncode != 0:
            raise RuntimeError(f"{container}: {action} failed: {result.stderr.strip()}")
        return result.stdout

    props = check(run("exec", container, "cat", "/data/server.properties"), "reading server.properties")
    world = next((line.split("=", 1)[1].strip() for line in props.splitlines()
                  if line.startswith("level-name=")), "")
    if not world:
        raise RuntimeError(f"{container}: level-name missing from server.properties")

    for pack, kind in ((packs.bp, "behavior"), (packs.rp, "resource")):
        src, uuid = pack.path, pack.uuid
        dest = f"/data/{kind}_packs/{src.name}"
        check(run("exec", container, "rm", "-rf", dest), f"removing old {dest}")
        check(run("cp", f"{src}/.", f"{container}:{dest}"), f"copying {src.name}")
        check(run("exec", container, "chown", "-R", "1000:1000", dest), f"chown {dest}")

        list_path = f"/data/worlds/{world}/world_{kind}_packs.json"
        existing = run("exec", container, "cat", list_path)
        entries = json.loads(existing.stdout) if existing.returncode == 0 and existing.stdout.strip() else []
        entry = next((p for p in entries if p.get("pack_id") == uuid), None)
        if entry is None:
            entries.append({"pack_id": uuid, "version": list(version)})
        else:
            entry["version"] = list(version)
        check(run("exec", "-i", container, "sh", "-c", 'cat > "$1"', "sh", list_path,
                  input=json.dumps(entries, indent=2) + "\n"), f"writing {list_path}")
        print(f"  [OK] {container}: {src.name} v{version_to_str(version)} active in world '{world}'")

    if "texturepack-required=true" not in props.splitlines():
        check(run("exec", container, "sed", "-i", "s/^texturepack-required=.*/texturepack-required=true/",
                  "/data/server.properties"), "requiring resource pack")
        print(f"  [OK] {container}: texturepack-required=true")

    answer = confirm(f"Restart {container} now? Connected players will be disconnected. [y/N] ")
    if answer.strip().lower() == "y":
        check(run("restart", container), "restart")
        print(f"  [OK] {container}: restarted")
    else:
        print(f"  [SKIP] {container}: not restarted; the new version loads on its next restart")


def restart_confirmer(assume_yes):
    """Answer each container-restart prompt: interactively, or 'y' under --yes."""
    if not assume_yes:
        return input

    def confirm(prompt):
        print(prompt + "y (--yes)")
        return "y"
    return confirm


def install(rev=True, rev_part="patch", explicit_version=None, servers=(), assume_yes=False):
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

    packs = AddonPacks.load(REPO_ROOT)

    if not packs.bp.path.is_dir() or not packs.rp.path.is_dir():
        print(f"[ERROR] Source packs missing in {REPO_ROOT}", file=sys.stderr)
        return 1

    mojang_roots = com_mojang_roots()
    if not mojang_roots:
        print("[ERROR] No local Minecraft Bedrock installation found.", file=sys.stderr)
        return 1

    deployed_count = 0
    for root in mojang_roots:
        print(f"\nInstalling to Minecraft root: {root}")

        # 1. Global development packs
        dev_bp = root / "development_behavior_packs" / packs.bp.name
        dev_rp = root / "development_resource_packs" / packs.rp.name
        packs.bp.copy_to(dev_bp)
        packs.rp.copy_to(dev_rp)
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
                        entries = read_json(wb_json)
                        if any(packs.bp.uuid in p.get("pack_id", "") for p in entries):
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
                            packs.bp.copy_to(bp_folder)
                            updated_world = True

                if w_rp.is_dir():
                    for rp_folder in w_rp.glob("*"):
                        if (rp_folder / "entity/monster_truck.entity.json").exists() or "MonsterTru" in rp_folder.name:
                            packs.rp.copy_to(rp_folder)
                            updated_world = True

                # Synchronize world pack versions in world_behavior_packs.json & world_resource_packs.json
                synced_manifests = sync_world_pack_versions(world, target_ver, packs)

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

    failed = False
    for name in servers:
        print(f"\nInstalling to server: {SERVER_CONTAINERS[name]}")
        try:
            install_to_server(name, target_ver, packs, confirm=restart_confirmer(assume_yes))
        except (RuntimeError, OSError, json.JSONDecodeError) as error:
            print(f"[ERROR] {error}", file=sys.stderr)
            failed = True
    return 1 if failed else 0

def main():
    parser = argparse.ArgumentParser(description="Install Monster Truck add-on with version revving and sync verification.")
    parser.add_argument("--rev", action="store_true", default=True, help="Rev patch version before installing (default)")
    parser.add_argument("--no-rev", dest="rev", action="store_false", help="Install current version without revving")
    parser.add_argument("--rev-minor", action="store_true", help="Rev minor version before installing")
    parser.add_argument("--rev-major", action="store_true", help="Rev major version before installing")
    parser.add_argument("--set-version", help="Set explicit version before installing e.g. 1.1.0")
    parser.add_argument("--check", action="store_true", help="Only verify version sync between repo and installed game")
    parser.add_argument("--servers", default="",
                        help="Also deploy to Docker servers, comma-separated: " + ",".join(SERVER_CONTAINERS))
    parser.add_argument("--yes", action="store_true",
                        help="Restart each --servers container without asking (disconnects connected players)")

    args = parser.parse_args()
    servers = [s.strip() for s in args.servers.split(",") if s.strip()]
    unknown = [s for s in servers if s not in SERVER_CONTAINERS]
    if unknown:
        parser.error(f"unknown server(s): {', '.join(unknown)}")

    if args.check:
        report = print_status_report(REPO_ROOT)
        sys.exit(0 if report["in_sync"] else 1)

    part = "patch"
    if args.rev_major:
        part = "major"
    elif args.rev_minor:
        part = "minor"

    return install(rev=args.rev, rev_part=part, explicit_version=args.set_version, servers=servers,
                   assume_yes=args.yes)

if __name__ == "__main__":
    sys.exit(main())
