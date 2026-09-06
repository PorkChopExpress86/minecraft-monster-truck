import json
from pathlib import Path
import pytest
from scripts.test_in_game import (
    sync_addon_to_development_packs,
    scan_content_log,
    run_in_game_test,
    TestReport,
)

@pytest.fixture
def mock_repo(tmp_path):
    repo_root = tmp_path / "repo"
    bp_src = repo_root / "behavior_packs" / "MonsterTruck_BP"
    rp_src = repo_root / "resource_packs" / "MonsterTruck_RP"
    bp_src.mkdir(parents=True)
    rp_src.mkdir(parents=True)

    bp_manifest = {"format_version": 2, "header": {"name": "Monster Truck BP"}}
    rp_manifest = {"format_version": 2, "header": {"name": "Monster Truck RP"}}
    (bp_src / "manifest.json").write_text(json.dumps(bp_manifest))
    (rp_src / "manifest.json").write_text(json.dumps(rp_manifest))
    return repo_root

def test_sync_addon_to_development_packs(mock_repo, tmp_path):
    mojang_dir = tmp_path / "com.mojang"
    bp_dest, rp_dest = sync_addon_to_development_packs(repo_root=mock_repo, mojang_dir=mojang_dir)

    assert bp_dest.exists()
    assert rp_dest.exists()
    assert (bp_dest / "manifest.json").exists()
    assert (rp_dest / "manifest.json").exists()
    assert json.loads((bp_dest / "manifest.json").read_text())["header"]["name"] == "Monster Truck BP"
    assert json.loads((rp_dest / "manifest.json").read_text())["header"]["name"] == "Monster Truck RP"

def test_scan_content_log_detects_errors(tmp_path):
    log_file = tmp_path / "content_log.txt"
    log_file.write_text(
        "[2026-09-06 12:00:00:100 INFO][General] Loading world\n"
        "[2026-09-06 12:00:01:200 ERROR][Entity] blake:monster_truck: invalid component\n"
        "[2026-09-06 12:00:02:300 WARNING][Resource] Texture missing for monster_truck\n",
        encoding="utf-8"
    )

    result = scan_content_log(log_file)
    assert result.has_errors is True
    assert len(result.errors) == 1
    assert "blake:monster_truck: invalid component" in result.errors[0]
    assert len(result.warnings) == 1
    assert "Texture missing" in result.warnings[0]

def test_scan_content_log_clean_with_offset(tmp_path):
    log_file = tmp_path / "content_log.txt"
    initial_content = "[2026-09-06 11:00:00:000 ERROR][Old] Past error\n"
    log_file.write_text(initial_content, encoding="utf-8")
    offset = len(initial_content)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("[2026-09-06 12:00:00:000 INFO][General] Clean start\n")

    result = scan_content_log(log_file, start_offset=offset)
    assert result.has_errors is False
    assert len(result.errors) == 0
    assert len(result.warnings) == 0

def test_run_in_game_test_dry_run(mock_repo, tmp_path):
    mojang_dir = tmp_path / "com.mojang"
    log_file = tmp_path / "content_log.txt"
    log_file.write_text("[INFO] World loaded cleanly\n")
    output_dir = tmp_path / "out"

    report = run_in_game_test(
        repo_root=mock_repo,
        mojang_dir=mojang_dir,
        content_log_path=log_file,
        output_dir=output_dir,
        dry_run=True,
    )

    assert isinstance(report, TestReport)
    assert report.passed is True
    assert report.errors_count == 0
    assert report.warnings_count == 0
    assert output_dir.exists()

def test_run_in_game_test_fails_on_content_log_error(mock_repo, tmp_path):
    mojang_dir = tmp_path / "com.mojang"
    log_file = tmp_path / "content_log.txt"
    log_file.write_text("[ERROR][Entity] blake:monster_truck: invalid component\n")
    output_dir = tmp_path / "out"

    report = run_in_game_test(
        repo_root=mock_repo,
        mojang_dir=mojang_dir,
        content_log_path=log_file,
        output_dir=output_dir,
        dry_run=True,
        initial_log_offset=0,
    )

    assert report.passed is False
    assert report.errors_count == 1
    assert len(report.error_details) == 1

def test_run_in_game_test_fails_on_missing_texture_warning(mock_repo, tmp_path):
    mojang_dir = tmp_path / "com.mojang"
    log_file = tmp_path / "content_log.txt"
    log_file.write_text("[WARNING][Resource] Texture missing for monster_truck\n")
    output_dir = tmp_path / "out"

    report = run_in_game_test(
        repo_root=mock_repo,
        mojang_dir=mojang_dir,
        content_log_path=log_file,
        output_dir=output_dir,
        dry_run=True,
        initial_log_offset=0,
    )

    assert report.passed is False
    assert report.warnings_count == 1
