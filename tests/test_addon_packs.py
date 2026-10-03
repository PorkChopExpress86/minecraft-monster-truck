"""The add-on's two packs as one module: paths from testing/bedrock.json, manifests, versions, copies, test staging."""
import json

import pytest

from scripts import bedrock_test
from scripts.addon_packs import AddonPacks, PackConfigError, com_mojang_roots, read_json, write_json
from scripts.validate_project import ProjectValidator
from scripts.version_manager import get_repo_version, set_repo_version

BP_ID = "11111111-1111-4111-8111-111111111111"
RP_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def repo(tmp_path):
    """A tmp repo whose packs live at non-default paths named by its own testing/bedrock.json."""
    root = tmp_path / "repo"
    write_json(root / "testing/bedrock.json", {"behavior_pack": "packs/Cart_BP", "resource_pack": "packs/Cart_RP"})
    write_json(root / "packs/Cart_BP/manifest.json", {
        "format_version": 2,
        "header": {"uuid": BP_ID, "version": [1, 2, 3], "min_engine_version": [1, 26, 40]},
        "modules": [{"type": "script", "entry": "scripts/main.js", "version": [1, 2, 3]}],
        "dependencies": [{"uuid": RP_ID, "version": [1, 2, 3]},
                         {"module_name": "@minecraft/server", "version": "2.10.0"}],
    })
    (root / "packs/Cart_BP/scripts").mkdir()
    (root / "packs/Cart_BP/scripts/main.js").write_text("// cart")
    # A BOM-prefixed manifest, as some editors save it, still reads.
    (root / "packs/Cart_RP").mkdir()
    (root / "packs/Cart_RP/manifest.json").write_text("﻿" + json.dumps({
        "format_version": 2,
        "header": {"uuid": RP_ID, "version": [1, 2, 3]},
        "modules": [{"type": "resources", "version": [1, 2, 3]}],
    }), encoding="utf-8")
    return root


def test_packs_are_located_by_testing_config_and_identified_by_their_manifests(repo):
    packs = AddonPacks.load(repo)
    assert packs.bp.path == repo / "packs/Cart_BP"
    assert packs.rp.path == repo / "packs/Cart_RP"
    assert (packs.bp.name, packs.rp.name) == ("Cart_BP", "Cart_RP")
    assert (packs.bp.uuid, packs.rp.uuid) == (BP_ID, RP_ID)
    assert packs.bp.version == [1, 2, 3]
    assert packs.rp.manifest["modules"][0]["type"] == "resources"


def test_a_loaded_config_can_be_supplied_instead_of_read(repo, tmp_path):
    other = tmp_path / "other"
    packs = AddonPacks.load(other, {"behavior_pack": "b", "resource_pack": "r"})
    assert (packs.bp.path, packs.rp.path) == (other / "b", other / "r")


def test_repo_without_testing_config_uses_the_default_pack_folders(tmp_path):
    packs = AddonPacks.load(tmp_path)
    assert packs.bp.path == tmp_path / "behavior_packs/MonsterTruck_BP"
    assert packs.rp.path == tmp_path / "resource_packs/MonsterTruck_RP"


@pytest.mark.parametrize("config_text, problem", [
    ("{not json", "Cannot read"),
    ('{"behavior_pack": "packs/Cart_BP"}', "must name behavior_pack and resource_pack"),
    ("[]", "must name behavior_pack and resource_pack"),
])
def test_a_broken_testing_config_is_one_clear_error_for_every_pack_tool(repo, config_text, problem):
    (repo / "testing/bedrock.json").write_text(config_text, encoding="utf-8")
    with pytest.raises(PackConfigError, match=problem):
        AddonPacks.load(repo)
    with pytest.raises(PackConfigError, match=problem):
        get_repo_version(repo)
    with pytest.raises(PackConfigError, match=problem):
        set_repo_version([2, 0, 0], repo)
    validator = ProjectValidator(repo_root=repo)
    errors = validator.validate_all()
    assert any(problem in error for error in errors), "the validator reports it as one of its own errors"


def test_set_version_revs_headers_modules_and_the_resource_pack_dependency(repo):
    packs = AddonPacks.load(repo)
    packs.set_version([2, 0, 0])
    bp, rp = packs.bp.manifest, packs.rp.manifest
    assert bp["header"]["version"] == rp["header"]["version"] == [2, 0, 0]
    assert bp["modules"][0]["version"] == rp["modules"][0]["version"] == [2, 0, 0]
    assert bp["dependencies"][0] == {"uuid": RP_ID, "version": [2, 0, 0]}
    assert bp["dependencies"][1] == {"module_name": "@minecraft/server", "version": "2.10.0"}, \
        "Script API module versions are not add-on versions"
    assert packs.bp.manifest_path.read_text(encoding="utf-8").endswith("}\n")


def test_copy_to_replaces_the_destination_with_the_pack(repo, tmp_path):
    packs = AddonPacks.load(repo)
    dest = tmp_path / "game/development_behavior_packs/Cart_BP"
    (dest / "stale").mkdir(parents=True)
    packs.bp.copy_to(dest)
    assert not (dest / "stale").exists()
    assert (dest / "scripts/main.js").read_text() == "// cart"


def test_stage_test_pack_installs_renamed_copies_and_activates_them(repo, tmp_path):
    packs = AddonPacks.load(repo)
    world = tmp_path / "world"
    harness = world / "behavior_packs/harness"
    (harness / "scripts").mkdir(parents=True)
    packs.stage_test_pack(world, world / "behavior_packs/test_bp", world / "resource_packs/test_rp",
                          {"run_id": "r1"}, harness / "scripts/run_config.js", pack_ids=("test-bp", "test-rp"),
                          extra_behavior_packs=[{"pack_id": "harness", "version": [1, 0, 0]}])
    staged_bp = read_json(world / "behavior_packs/test_bp/manifest.json")
    staged_rp = read_json(world / "resource_packs/test_rp/manifest.json")
    assert (staged_bp["header"]["uuid"], staged_rp["header"]["uuid"]) == ("test-bp", "test-rp")
    assert staged_bp["dependencies"][0]["uuid"] == "test-rp"
    assert (harness / "scripts/run_config.js").read_text() == 'export const run = {"run_id": "r1"};\n'
    assert read_json(world / "world_behavior_packs.json") == [
        {"pack_id": "test-bp", "version": [1, 2, 3]}, {"pack_id": "harness", "version": [1, 0, 0]}]
    assert read_json(world / "world_resource_packs.json") == [{"pack_id": "test-rp", "version": [1, 2, 3]}]
    assert packs.bp.uuid == BP_ID, "the source pack is never modified"


def test_stage_test_pack_keeps_ids_and_lets_the_caller_customize_the_behavior_pack(repo, tmp_path):
    packs = AddonPacks.load(repo)
    world = tmp_path / "world"
    original_rp = (repo / "packs/Cart_RP/manifest.json").read_bytes()

    def add_driver(pack, manifest):
        (pack / "scripts/driver").mkdir()
        manifest["modules"][0]["entry"] = "scripts/driver_entry.js"

    packs.stage_test_pack(world, world / "behavior_packs/Cart_BP", world / "resource_packs/Cart_RP",
                          {"run_id": "r2"}, world / "behavior_packs/Cart_BP/scripts/driver/run_config.js",
                          customize_bp=add_driver)
    staged = read_json(world / "behavior_packs/Cart_BP/manifest.json")
    assert staged["header"]["uuid"] == BP_ID
    assert staged["modules"][0]["entry"] == "scripts/driver_entry.js"
    assert (world / "resource_packs/Cart_RP/manifest.json").read_bytes() == original_rp
    assert "r2" in (world / "behavior_packs/Cart_BP/scripts/driver/run_config.js").read_text()
    assert read_json(world / "world_behavior_packs.json") == [{"pack_id": BP_ID, "version": [1, 2, 3]}]
    assert read_json(world / "world_resource_packs.json") == [{"pack_id": RP_ID, "version": [1, 2, 3]}]


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """Fake Windows (GDK and legacy UWP) and Linux (flatpak, native mcpelauncher) game data locations."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    users = tmp_path / "roaming/Minecraft Bedrock/Users"
    return {
        "gdk": users / "1234/games/com.mojang",
        "shared": users / "Shared/games/com.mojang",
        "legacy": tmp_path / "local/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang",
        "flatpak": tmp_path / "home/.var/app/io.mrarm.mcpelauncher/data/mcpelauncher/games/com.mojang",
        "native": tmp_path / "home/.local/share/mcpelauncher/games/com.mojang",
    }


def initialize(path):
    (path / "minecraftpe").mkdir(parents=True)
    (path / "minecraftpe/options.txt").write_text("content_log_file:1\n")


def test_com_mojang_roots_lists_every_install_in_platform_order(machine):
    assert com_mojang_roots() == []
    for name in ("native", "legacy", "flatpak", "gdk"):
        machine[name].mkdir(parents=True)
    assert com_mojang_roots() == [machine[name].resolve() for name in ("gdk", "legacy", "flatpak", "native")]


def test_account_roots_require_options_and_prefer_the_newest_initialized_install(machine):
    for name in machine:
        machine[name].mkdir(parents=True)
    assert com_mojang_roots(require_options=True) == []
    initialize(machine["shared"])
    initialize(machine["native"])
    assert com_mojang_roots(require_options=True) == [machine["native"].resolve()], "Shared is never an account"
    initialize(machine["legacy"])
    assert com_mojang_roots(require_options=True) == [machine["legacy"].resolve()]
    initialize(machine["gdk"])
    assert com_mojang_roots(require_options=True) == [machine["gdk"].resolve()]


def test_linux_launcher_roots_are_listed_flatpak_first(machine, monkeypatch):
    monkeypatch.delenv("APPDATA")
    monkeypatch.delenv("LOCALAPPDATA")
    assert com_mojang_roots() == []
    machine["flatpak"].mkdir(parents=True)
    assert com_mojang_roots() == [machine["flatpak"].resolve()]
    machine["native"].mkdir(parents=True)
    assert com_mojang_roots() == [machine["flatpak"].resolve(), machine["native"].resolve()]


def add_world(com_mojang, name):
    world = com_mojang / "minecraftWorlds" / name
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"")
    (world / "levelname.txt").write_text(name.title())
    return str(world.resolve())


def test_discovery_lists_windows_game_folders_and_initialized_linux_accounts(machine):
    expected = [add_world(machine[name], name) for name in ("gdk", "shared", "legacy", "flatpak")]
    add_world(machine["native"], "native")  # never initialized: not a launcher account
    initialize(machine["flatpak"])
    for name in ("flatpak", "native", "gdk"):
        (machine[name] / "logs").mkdir()
    result = bedrock_test.discover()
    assert [world["path"] for world in result["worlds"]] == expected
    assert result["worlds"][0]["name"] == "Gdk"
    # mcpelauncher keeps logs inside com.mojang; Windows logs live beside the account folders.
    assert result["log_directories"] == [str(machine["flatpak"].resolve() / "logs")]


def test_windows_locations_are_skipped_when_their_environment_is_unset(machine, monkeypatch):
    monkeypatch.delenv("APPDATA")
    monkeypatch.delenv("LOCALAPPDATA")
    machine["gdk"].mkdir(parents=True)
    initialize(machine["flatpak"])
    assert com_mojang_roots() == [machine["flatpak"].resolve()]
    assert com_mojang_roots(require_options=True) == [machine["flatpak"].resolve()]
