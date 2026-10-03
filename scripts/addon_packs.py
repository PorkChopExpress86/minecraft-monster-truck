"""The add-on's behavior and resource packs, and where local Minecraft keeps its game data.

Pack folders are named by testing/bedrock.json (keys behavior_pack / resource_pack); identity and
version always come from each pack's manifest.json. Every script that reads, versions, copies, or
stages the packs goes through AddonPacks.
"""
import json
import os
from pathlib import Path
import shutil

try:
    from .bedrock_linux import data_dir as launcher_data_dir
except ImportError:
    from bedrock_linux import data_dir as launcher_data_dir


REPO_ROOT = Path(__file__).resolve().parents[1]
# Used only by a repo without testing/bedrock.json (fixture repos in tests).
DEFAULT_PACKS = {"behavior_pack": "behavior_packs/MonsterTruck_BP", "resource_pack": "resource_packs/MonsterTruck_RP"}
UWP_LOCAL_STATE = "Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"


class PackConfigError(ValueError):
    """testing/bedrock.json cannot be read or does not name both packs."""


def read_json(path):
    """Read JSON written by Minecraft, editors, or this repo (a UTF-8 byte-order mark is accepted)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class Pack:
    """One pack folder. Manifest fields are read fresh on each access, so a version rev is seen at once."""

    def __init__(self, path):
        self.path = Path(path)

    @property
    def name(self):
        return self.path.name

    @property
    def manifest_path(self):
        return self.path / "manifest.json"

    @property
    def manifest(self):
        return read_json(self.manifest_path)

    @property
    def uuid(self):
        return self.manifest["header"]["uuid"]

    @property
    def version(self):
        return self.manifest["header"]["version"]

    def copy_to(self, dest):
        """Replace dest with a fresh copy of this pack."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.path, dest)


class AddonPacks:
    def __init__(self, bp, rp):
        self.bp = bp
        self.rp = rp

    @classmethod
    def load(cls, root=None, config=None):
        """The packs of the repo at root; pass config when testing/bedrock.json is already loaded."""
        root = Path(root) if root else REPO_ROOT
        path = root / "testing/bedrock.json"
        if config is None:
            try:
                config = read_json(path) if path.is_file() else DEFAULT_PACKS
            except (OSError, ValueError) as error:
                raise PackConfigError(f"Cannot read {path}: {error}") from error
        try:
            return cls(Pack(root / config["behavior_pack"]), Pack(root / config["resource_pack"]))
        except (KeyError, TypeError) as error:
            raise PackConfigError(f"{path} must name behavior_pack and resource_pack folders") from error

    def set_version(self, version):
        """Write version into both manifests: headers, modules, and BP dependencies on pack versions.

        Script API module dependencies carry string versions and are left alone. A missing manifest is skipped.
        """
        version = [int(part) for part in version]
        rp_uuid = None
        if self.rp.manifest_path.is_file():
            rp = self.rp.manifest
            rp_uuid = rp.get("header", {}).get("uuid")
            if "header" in rp:
                rp["header"]["version"] = version
            for module in rp.get("modules", []):
                module["version"] = version
            write_json(self.rp.manifest_path, rp)
        if self.bp.manifest_path.is_file():
            bp = self.bp.manifest
            if "header" in bp:
                bp["header"]["version"] = version
            for module in bp.get("modules", []):
                module["version"] = version
            for dependency in bp.get("dependencies", []):
                if (rp_uuid is not None and dependency.get("uuid") == rp_uuid) or isinstance(dependency.get("version"), list):
                    dependency["version"] = version
            write_json(self.bp.manifest_path, bp)
        return version

    def stage_test_pack(self, world, bp_dest, rp_dest, run, run_config, *, pack_ids=None, customize_bp=None,
                        extra_behavior_packs=()):
        """Install test copies of both packs into world and make them the world's active packs.

        pack_ids=(bp_id, rp_id) gives the copies their own identities (and repoints the BP's dependency on
        the RP) so they never collide with an installed release. customize_bp(pack_dir, manifest) may add
        files to the BP copy and edit its manifest before it is written. run is written to run_config as
        the JavaScript module `export const run = {...};`. extra_behavior_packs are appended, in order, to
        world_behavior_packs.json after the BP copy.
        """
        source_bp, source_rp = self.bp.manifest, self.rp.manifest
        bp_id, rp_id = pack_ids or (source_bp["header"]["uuid"], source_rp["header"]["uuid"])
        self.bp.copy_to(bp_dest)
        self.rp.copy_to(rp_dest)
        bp = read_json(Path(bp_dest) / "manifest.json")
        if pack_ids:
            bp["header"]["uuid"] = bp_id
            for dependency in bp.get("dependencies", []):
                if dependency.get("uuid") == source_rp["header"]["uuid"]:
                    dependency["uuid"] = rp_id
            rp = read_json(Path(rp_dest) / "manifest.json")
            rp["header"]["uuid"] = rp_id
            write_json(Path(rp_dest) / "manifest.json", rp)
        if customize_bp:
            customize_bp(Path(bp_dest), bp)
        if pack_ids or customize_bp:
            write_json(Path(bp_dest) / "manifest.json", bp)
        run_config = Path(run_config)
        run_config.parent.mkdir(parents=True, exist_ok=True)
        run_config.write_text("export const run = " + json.dumps(run) + ";\n", encoding="utf-8")
        world = Path(world)
        write_json(world / "world_behavior_packs.json",
                   [{"pack_id": bp_id, "version": source_bp["header"]["version"]}, *extra_behavior_packs])
        write_json(world / "world_resource_packs.json",
                   [{"pack_id": rp_id, "version": source_rp["header"]["version"]}])


def _installs():
    """Candidate com.mojang directories per install, in order: ("gdk", Windows GDK users), ("legacy", UWP),
    ("linux", mcpelauncher flatpak then native). Paths are unresolved and may not exist."""
    gdk, legacy = [], []
    if os.environ.get("APPDATA"):
        users = Path(os.environ["APPDATA"]) / "Minecraft Bedrock/Users"
        gdk = sorted(users.glob("*/games/com.mojang"))
    if os.environ.get("LOCALAPPDATA"):
        legacy = [Path(os.environ["LOCALAPPDATA"]) / UWP_LOCAL_STATE / "games/com.mojang"]
    linux = [launcher_data_dir() / "games/com.mojang", Path.home() / ".local/share/mcpelauncher/games/com.mojang"]
    return [("gdk", gdk), ("legacy", legacy), ("linux", linux)]


def _has_options(path):
    return (path / "minecraftpe/options.txt").is_file()


def com_mojang_roots(require_options=False, *, discovery=False):
    """Existing local com.mojang directories, resolved, in install order: Windows GDK users, legacy UWP,
    then the Linux mcpelauncher flatpak and native installs.

    require_options=True returns only initialized player accounts (minecraftpe/options.txt present; the GDK
    Shared folder is never one), taken from the first of those three installs that has any, so a stale
    legacy UWP account does not compete with a GDK one.

    discovery=True is the read-only view bedrock_test.discover reports: Windows game folders as found but
    only initialized Linux launcher accounts, as (root, logs) pairs. logs is the root's own logs folder
    when it exists and the root is a launcher install (mcpelauncher keeps logs inside com.mojang; Windows
    keeps them beside the account folders), else None.
    """
    installs = _installs()
    if require_options:
        for _, install in installs:
            accounts = [path.resolve() for path in install
                        if _has_options(path) and path.parents[1].name != "Shared"]
            if accounts:
                return accounts
        return []
    roots, found = [], []
    for name, install in installs:
        for path in install:
            if not path.is_dir() or path.resolve() in roots:
                continue
            if discovery and name == "linux" and not _has_options(path):
                continue
            roots.append(path.resolve())
            logs = path.resolve() / "logs"
            found.append((path.resolve(), logs if name == "linux" and logs.is_dir() else None))
    return found if discovery else roots
