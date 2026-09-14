"""Tests for version revving and sync verification across repo manifests and game targets."""
import json
from pathlib import Path
import pytest

from scripts.version_manager import (
    get_repo_version,
    set_repo_version,
    bump_version,
    version_to_str,
    str_to_version,
    check_version_sync,
    sync_world_pack_versions,
    BP_UUID,
    RP_UUID,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_version_helpers():
    assert version_to_str([1, 2, 3]) == "1.2.3"
    assert version_to_str([]) == "0.0.0"
    assert str_to_version("1.2.3") == [1, 2, 3]
    assert str_to_version("v2.0.1") == [2, 0, 1]
    assert str_to_version("3.1") == [3, 1, 0]

def test_repo_version_consistency():
    ver = get_repo_version(REPO_ROOT)
    assert len(ver) == 3
    assert all(isinstance(x, int) for x in ver)

    bp_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "manifest.json"
    rp_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "manifest.json"
    cfg_path = REPO_ROOT / "vehicle.config.json"

    bp = json.loads(bp_path.read_text(encoding="utf-8"))
    rp = json.loads(rp_path.read_text(encoding="utf-8"))
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    assert bp["header"]["version"] == ver
    assert rp["header"]["version"] == ver
    assert cfg["version"] == ver

    # BP module versions
    for mod in bp["modules"]:
        assert mod["version"] == ver

    # RP module version
    for mod in rp["modules"]:
        assert mod["version"] == ver

    # BP dependency on RP version
    rp_dep = next(d for d in bp["dependencies"] if d.get("uuid") == RP_UUID)
    assert rp_dep["version"] == ver

def test_bump_version_in_temp_repo(tmp_path):
    # Setup mock repo structure
    bp_dir = tmp_path / "behavior_packs" / "MonsterTruck_BP"
    rp_dir = tmp_path / "resource_packs" / "MonsterTruck_RP"
    bp_dir.mkdir(parents=True)
    rp_dir.mkdir(parents=True)

    bp_manifest = {
        "header": {"version": [1, 0, 0]},
        "modules": [{"version": [1, 0, 0]}],
        "dependencies": [{"uuid": RP_UUID, "version": [1, 0, 0]}]
    }
    rp_manifest = {
        "header": {"version": [1, 0, 0]},
        "modules": [{"version": [1, 0, 0]}]
    }
    cfg_json = {"version": [1, 0, 0]}

    (bp_dir / "manifest.json").write_text(json.dumps(bp_manifest), encoding="utf-8")
    (rp_dir / "manifest.json").write_text(json.dumps(rp_manifest), encoding="utf-8")
    (tmp_path / "vehicle.config.json").write_text(json.dumps(cfg_json), encoding="utf-8")

    # 1. Patch bump
    v_patch = bump_version("patch", repo_root=tmp_path)
    assert v_patch == [1, 0, 1]
    assert get_repo_version(tmp_path) == [1, 0, 1]

    # Verify BP updated
    bp_data = json.loads((bp_dir / "manifest.json").read_text(encoding="utf-8"))
    assert bp_data["header"]["version"] == [1, 0, 1]
    assert bp_data["modules"][0]["version"] == [1, 0, 1]
    assert bp_data["dependencies"][0]["version"] == [1, 0, 1]

    # Verify RP updated
    rp_data = json.loads((rp_dir / "manifest.json").read_text(encoding="utf-8"))
    assert rp_data["header"]["version"] == [1, 0, 1]
    assert rp_data["modules"][0]["version"] == [1, 0, 1]

    # 2. Minor bump
    v_minor = bump_version("minor", repo_root=tmp_path)
    assert v_minor == [1, 1, 0]
    assert get_repo_version(tmp_path) == [1, 1, 0]

    # 3. Major bump
    v_major = bump_version("major", repo_root=tmp_path)
    assert v_major == [2, 0, 0]
    assert get_repo_version(tmp_path) == [2, 0, 0]

    # 4. Explicit set
    v_explicit = bump_version(repo_root=tmp_path, explicit_version="3.4.5")
    assert v_explicit == [3, 4, 5]
    assert get_repo_version(tmp_path) == [3, 4, 5]

def test_sync_world_pack_versions(tmp_path):
    world_dir = tmp_path / "test_world"
    world_dir.mkdir()

    wbp = [{"pack_id": BP_UUID, "version": [1, 0, 0]}]
    wrp = [{"pack_id": RP_UUID, "version": [1, 0, 0]}]

    wbp_file = world_dir / "world_behavior_packs.json"
    wrp_file = world_dir / "world_resource_packs.json"
    wbp_file.write_text(json.dumps(wbp), encoding="utf-8")
    wrp_file.write_text(json.dumps(wrp), encoding="utf-8")

    updated = sync_world_pack_versions(world_dir, [1, 0, 2])
    assert updated is True

    updated_wbp = json.loads(wbp_file.read_text(encoding="utf-8"))
    updated_wrp = json.loads(wrp_file.read_text(encoding="utf-8"))
    assert updated_wbp[0]["version"] == [1, 0, 2]
    assert updated_wrp[0]["version"] == [1, 0, 2]

def test_check_version_sync_detection(tmp_path):
    # Mock Mojang installation
    mojang_root = tmp_path / "com.mojang"
    dev_bp = mojang_root / "development_behavior_packs" / "MonsterTruck_BP"
    dev_rp = mojang_root / "development_resource_packs" / "MonsterTruck_RP"
    dev_bp.mkdir(parents=True)
    dev_rp.mkdir(parents=True)

    (dev_bp / "manifest.json").write_text(json.dumps({"header": {"version": [1, 0, 0]}}), encoding="utf-8")
    (dev_rp / "manifest.json").write_text(json.dumps({"header": {"version": [1, 0, 0]}}), encoding="utf-8")

    # Repo version is 1.0.0 -> Should be in sync
    res = check_version_sync(repo_root=REPO_ROOT, mojang_roots=[mojang_root])
    current_repo_v = get_repo_version(REPO_ROOT)
    if current_repo_v == [1, 0, 0]:
        assert res["in_sync"] is True

    # If installed dev packs have older version -> Should report out of sync
    (dev_bp / "manifest.json").write_text(json.dumps({"header": {"version": [0, 9, 0]}}), encoding="utf-8")
    res_mismatch = check_version_sync(repo_root=REPO_ROOT, mojang_roots=[mojang_root])
    assert res_mismatch["in_sync"] is False
    assert "OUT OF SYNC" in res_mismatch["summary"]
