"""Version manager and sync verification for the Monster Truck Minecraft Bedrock Add-on."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

BP_UUID = "bc617e1c-0c92-4f91-ab9b-241d7ef141d0"
RP_UUID = "f6fc3675-bf88-45bd-9348-2c75d1e8573e"

def version_to_str(ver):
    """Convert version array [major, minor, patch] to string 'major.minor.patch'."""
    if not ver or not isinstance(ver, (list, tuple)):
        return "0.0.0"
    return ".".join(str(int(x)) for x in ver)

def str_to_version(ver_str):
    """Parse string '1.0.0' or 'v1.0.0' to [1, 0, 0]."""
    cleaned = ver_str.strip().lstrip("vV")
    parts = cleaned.split(".")
    if len(parts) < 3:
        parts.extend(["0"] * (3 - len(parts)))
    return [int(parts[0]), int(parts[1]), int(parts[2])]

def get_repo_version(repo_root=None):
    """Get the canonical add-on version from behavior pack manifest or config."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    bp_manifest_path = root / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    if bp_manifest_path.is_file():
        try:
            data = json.loads(bp_manifest_path.read_text(encoding="utf-8"))
            ver = data.get("header", {}).get("version")
            if isinstance(ver, list) and len(ver) == 3:
                return [int(x) for x in ver]
        except Exception:
            pass

    cfg_json = root / "vehicle.config.json"
    if cfg_json.is_file():
        try:
            data = json.loads(cfg_json.read_text(encoding="utf-8"))
            ver = data.get("version")
            if isinstance(ver, list) and len(ver) == 3:
                return [int(x) for x in ver]
            elif isinstance(ver, str):
                return str_to_version(ver)
        except Exception:
            pass

    return [1, 0, 0]

def set_repo_version(new_version, repo_root=None):
    """Update version across manifests and config files."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    new_ver = [int(x) for x in new_version]
    if len(new_ver) != 3:
        raise ValueError(f"Version must have 3 integers [major, minor, patch], got {new_version}")

    # 1. Behavior Pack manifest
    bp_manifest_path = root / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    if bp_manifest_path.is_file():
        bp_data = json.loads(bp_manifest_path.read_text(encoding="utf-8"))
        if "header" in bp_data:
            bp_data["header"]["version"] = new_ver
        if "modules" in bp_data:
            for mod in bp_data["modules"]:
                mod["version"] = new_ver
        if "dependencies" in bp_data:
            for dep in bp_data["dependencies"]:
                if dep.get("uuid") == RP_UUID or "version" in dep and isinstance(dep.get("version"), list):
                    dep["version"] = new_ver
        bp_manifest_path.write_text(json.dumps(bp_data, indent=2) + "\n", encoding="utf-8")

    # 2. Resource Pack manifest
    rp_manifest_path = root / "resource_packs" / "MonsterTruck_RP" / "manifest.json"
    if rp_manifest_path.is_file():
        rp_data = json.loads(rp_manifest_path.read_text(encoding="utf-8"))
        if "header" in rp_data:
            rp_data["header"]["version"] = new_ver
        if "modules" in rp_data:
            for mod in rp_data["modules"]:
                mod["version"] = new_ver
        rp_manifest_path.write_text(json.dumps(rp_data, indent=2) + "\n", encoding="utf-8")

    # 3. vehicle.config.json
    cfg_json_path = root / "vehicle.config.json"
    if cfg_json_path.is_file():
        cfg_json = json.loads(cfg_json_path.read_text(encoding="utf-8"))
        cfg_json["version"] = new_ver
        cfg_json_path.write_text(json.dumps(cfg_json, indent=2) + "\n", encoding="utf-8")

    # 4. vehicle.config.yaml
    cfg_yaml_path = root / "vehicle.config.yaml"
    if cfg_yaml_path.is_file():
        try:
            with open(cfg_yaml_path, "r", encoding="utf-8") as f:
                cfg_yaml = yaml.safe_load(f) or {}
            cfg_yaml["version"] = new_ver
            with open(cfg_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg_yaml, f, sort_keys=False)
        except Exception:
            pass

    return new_ver

def bump_version(part="patch", repo_root=None, explicit_version=None):
    """Bump patch, minor, or major version in repository."""
    if explicit_version:
        new_ver = str_to_version(explicit_version) if isinstance(explicit_version, str) else [int(x) for x in explicit_version]
    else:
        current = get_repo_version(repo_root)
        major, minor, patch = current
        if part == "major":
            new_ver = [major + 1, 0, 0]
        elif part == "minor":
            new_ver = [major, minor + 1, 0]
        else: # patch
            new_ver = [major, minor, patch + 1]

    return set_repo_version(new_ver, repo_root)

def find_com_mojang_roots():
    """Find all local com.mojang directories on the machine."""
    roots = []
    # GDK Roaming path
    roaming_users = Path(os.environ.get("APPDATA", "")) / "Minecraft Bedrock/Users"
    if roaming_users.is_dir():
        for user_dir in roaming_users.glob("*/games/com.mojang"):
            if user_dir.parent.name != "Shared":
                roots.append(user_dir.resolve())

    # Legacy UWP LocalAppData path
    legacy = (Path(os.environ.get("LOCALAPPDATA", "")) /
              "Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang")
    if legacy.is_dir() and legacy.resolve() not in roots:
        roots.append(legacy.resolve())

    return roots

def get_installed_versions(mojang_roots=None):
    """Scan local Minecraft Bedrock installation and retrieve versions across all targets."""
    roots = mojang_roots if mojang_roots is not None else find_com_mojang_roots()
    targets = []

    for root in roots:
        # 1. Global Dev Behavior Pack
        dev_bp = root / "development_behavior_packs" / "MonsterTruck_BP" / "manifest.json"
        if dev_bp.is_file():
            try:
                data = json.loads(dev_bp.read_text(encoding="utf-8"))
                ver = data.get("header", {}).get("version")
                targets.append({
                    "target": "development_behavior_packs",
                    "location": str(dev_bp.parent),
                    "version": ver,
                    "version_str": version_to_str(ver)
                })
            except Exception:
                pass

        # 2. Global Dev Resource Pack
        dev_rp = root / "development_resource_packs" / "MonsterTruck_RP" / "manifest.json"
        if dev_rp.is_file():
            try:
                data = json.loads(dev_rp.read_text(encoding="utf-8"))
                ver = data.get("header", {}).get("version")
                targets.append({
                    "target": "development_resource_packs",
                    "location": str(dev_rp.parent),
                    "version": ver,
                    "version_str": version_to_str(ver)
                })
            except Exception:
                pass

        # 3. Worlds
        worlds_dir = root / "minecraftWorlds"
        if worlds_dir.is_dir():
            for world in worlds_dir.glob("*"):
                if not world.is_dir():
                    continue
                wname_file = world / "levelname.txt"
                wname = wname_file.read_text(encoding="utf-8-sig").strip() if wname_file.is_file() else world.name

                # Check world_behavior_packs.json
                wbp_file = world / "world_behavior_packs.json"
                if wbp_file.is_file():
                    try:
                        packs = json.loads(wbp_file.read_text(encoding="utf-8"))
                        for p in packs:
                            if p.get("pack_id") == BP_UUID:
                                targets.append({
                                    "target": f"world_bp_entry:{wname}",
                                    "location": str(world),
                                    "world_name": wname,
                                    "version": p.get("version"),
                                    "version_str": version_to_str(p.get("version"))
                                })
                    except Exception:
                        pass

                # Check world_resource_packs.json
                wrp_file = world / "world_resource_packs.json"
                if wrp_file.is_file():
                    try:
                        packs = json.loads(wrp_file.read_text(encoding="utf-8"))
                        for p in packs:
                            if p.get("pack_id") == RP_UUID:
                                targets.append({
                                    "target": f"world_rp_entry:{wname}",
                                    "location": str(world),
                                    "world_name": wname,
                                    "version": p.get("version"),
                                    "version_str": version_to_str(p.get("version"))
                                })
                    except Exception:
                        pass

    return targets

def sync_world_pack_versions(world_dir: Path, new_version: list):
    """Synchronize pack version inside world_behavior_packs.json and world_resource_packs.json."""
    new_ver = [int(x) for x in new_version]
    updated = False

    wbp_file = world_dir / "world_behavior_packs.json"
    if wbp_file.is_file():
        try:
            packs = json.loads(wbp_file.read_text(encoding="utf-8"))
            found = False
            for p in packs:
                if p.get("pack_id") == BP_UUID:
                    p["version"] = new_ver
                    found = True
            if found:
                wbp_file.write_text(json.dumps(packs, indent=2) + "\n", encoding="utf-8")
                updated = True
        except Exception:
            pass

    wrp_file = world_dir / "world_resource_packs.json"
    if wrp_file.is_file():
        try:
            packs = json.loads(wrp_file.read_text(encoding="utf-8"))
            found = False
            for p in packs:
                if p.get("pack_id") == RP_UUID:
                    p["version"] = new_ver
                    found = True
            if found:
                wrp_file.write_text(json.dumps(packs, indent=2) + "\n", encoding="utf-8")
                updated = True
        except Exception:
            pass

    return updated

def check_version_sync(repo_root=None, mojang_roots=None):
    """Compare latest finished repo version against all installed Minecraft targets."""
    repo_ver = get_repo_version(repo_root)
    repo_str = version_to_str(repo_ver)
    targets = get_installed_versions(mojang_roots)

    if not targets:
        return {
            "repo_version": repo_ver,
            "repo_version_str": repo_str,
            "is_installed": False,
            "in_sync": False,
            "targets": [],
            "summary": f"Add-on not currently installed in local Minecraft Bedrock (Repo finished version: v{repo_str})"
        }

    all_match = True
    verified_targets = []
    for t in targets:
        matches = (t.get("version") == repo_ver)
        if not matches:
            all_match = False
        verified_targets.append({
            **t,
            "matches": matches,
            "expected_version": repo_ver,
            "expected_version_str": repo_str
        })

    # Pick representative installed version string
    installed_versions = {t["version_str"] for t in targets}
    installed_summary_str = ", ".join(sorted(installed_versions))

    if all_match:
        summary = f"IN SYNC: All {len(targets)} installed locations match finished repo version v{repo_str}"
    else:
        summary = f"OUT OF SYNC: Finished repo is v{repo_str}, but installed versions are [{installed_summary_str}]"

    return {
        "repo_version": repo_ver,
        "repo_version_str": repo_str,
        "is_installed": True,
        "in_sync": all_match,
        "installed_versions": list(installed_versions),
        "targets": verified_targets,
        "summary": summary
    }

def print_status_report(repo_root=None):
    """Print human-readable status report of version sync."""
    report = check_version_sync(repo_root)
    repo_str = report["repo_version_str"]
    print("=" * 60)
    print("MONSTER TRUCK ADD-ON VERSION SYNC STATUS")
    print("=" * 60)
    print(f"Finished Repo Version : v{repo_str}")
    print(f"Sync Status           : {'MATCH (IN SYNC)' if report['in_sync'] else 'MISMATCH (OUT OF SYNC)'}")
    print(f"Summary               : {report['summary']}")
    print("-" * 60)

    if report["targets"]:
        print("Installed Locations:")
        for t in report["targets"]:
            status = "[OK]  " if t["matches"] else "[FAIL]"
            print(f"  {status} {t['target']} -> v{t['version_str']}")
    else:
        print("No installed game targets detected.")
    print("=" * 60)
    return report

def main():
    parser = argparse.ArgumentParser(description="Manage and verify add-on version revving.")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # get
    subparsers.add_parser("get", help="Get current repository version")

    # status
    subparsers.add_parser("status", help="Show full version sync status between repo and game")

    # check
    subparsers.add_parser("check", help="Exit 0 if in sync, exit 1 if out of sync")

    # bump
    bump_parser = subparsers.add_parser("bump", help="Bump version in repo manifests and configs")
    bump_parser.add_argument("part", choices=["patch", "minor", "major"], default="patch", nargs="?")

    # set
    set_parser = subparsers.add_parser("set", help="Set explicit version [major.minor.patch]")
    set_parser.add_argument("version", help="Explicit version string e.g. 1.0.1")

    args = parser.parse_args()

    if args.action == "get":
        print(version_to_str(get_repo_version()))
    elif args.action == "status":
        report = print_status_report()
        sys.exit(0 if report["in_sync"] else 1)
    elif args.action == "check":
        report = check_version_sync()
        print(report["summary"])
        sys.exit(0 if report["in_sync"] else 1)
    elif args.action == "bump":
        new_v = bump_version(args.part)
        print(f"Version revved to v{version_to_str(new_v)} ({args.part})")
    elif args.action == "set":
        new_v = bump_version(explicit_version=args.version)
        print(f"Version set to v{version_to_str(new_v)}")
    else:
        print_status_report()

if __name__ == "__main__":
    main()
