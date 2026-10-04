"""Headless Scenario Run orchestration (ADR-0016), with Docker replaced by a fake."""
import io
import json
from pathlib import Path
import struct
import subprocess
import zipfile

import nbtlib
import pytest

from scripts import bedrock_scenarios as scenarios

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN = "run1"


def marker(status, **extra):
    return "[2026-10-02 00:58:41:421 WARN] [Scripting] [SCENARIO]" + json.dumps(
        {"run_id": RUN, "status": status, **extra}) + "\n"


def test_all_scenarios_must_pass_and_finish():
    text = marker("PASS", scenario="smoke", checks=["spawned"]) + marker("DONE")
    result = scenarios.evaluate(text, RUN, ["smoke"])
    assert result["status"] == "passed"
    assert result["scenarios"]["smoke"] == {"status": "passed", "checks": ["spawned"]}


@pytest.mark.parametrize("text,expected", [
    (marker("FAIL", scenario="smoke", error="Truck did not spawn") + marker("DONE"), "smoke: Truck did not spawn"),
    (marker("DONE"), "smoke: no result reported"),
    (marker("PASS", scenario="smoke") + "[2026-10-02 WARN] [Json] bad component\n" + marker("DONE"),
     "[2026-10-02 WARN] [Json] bad component"),
])
def test_failures_missing_results_and_server_warnings_fail_the_run(text, expected):
    result = scenarios.evaluate(text, RUN, ["smoke"])
    assert result["status"] == "failed"
    assert expected in result["errors"]


def test_markers_from_other_runs_are_ignored():
    stale = marker("PASS", scenario="smoke").replace(RUN, "old") + marker("DONE").replace(RUN, "old")
    assert scenarios.evaluate(stale, RUN, ["smoke"])["status"] == "failed"


@pytest.fixture
def server_files(tmp_path, monkeypatch):
    archive = tmp_path / "server.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("bedrock_server", b"binary")
        zipped.writestr("server.properties", "level-name=Bedrock level\n")
    level = nbtlib.File({"LevelName": nbtlib.String("starter"), "GameType": nbtlib.Int(0),
                        "Difficulty": nbtlib.Int(2), "experiments": nbtlib.Compound({"gametest": nbtlib.Byte(0)}),
                        **{key: nbtlib.Byte(1) for key in (
                            "commandsEnabled", "MultiplayerGame", "MultiplayerGameIntent", "LANBroadcast",
                            "LANBroadcastIntent", "XBLBroadcastIntent", "PlatformBroadcastIntent")}})
    payload = io.BytesIO()
    level.write(payload, byteorder="little")
    starter = io.BytesIO()
    with zipfile.ZipFile(starter, "w") as zipped:
        zipped.writestr("level.dat", struct.pack("<II", 9, len(payload.getvalue())) + payload.getvalue())
    monkeypatch.setattr(scenarios, "server_zip", lambda root, server: archive)
    monkeypatch.setattr(scenarios, "template_bytes", lambda root: starter.getvalue())
    config = json.loads((REPO_ROOT / "testing/bedrock.json").read_text())
    # The fake server below reports only the smoke scenario.
    config["scenario_server"]["scenarios"] = ["smoke"]
    return config


def test_prepared_scenario_world_runs_the_driver_inside_a_test_copy_of_the_addon(server_files, tmp_path):
    data = scenarios.prepare_server(REPO_ROOT, server_files, RUN, tmp_path)
    world = data / "worlds" / scenarios.LEVEL
    level = nbtlib.File.parse(io.BytesIO((world / "level.dat").read_bytes()[8:]), byteorder="little")
    assert level["experiments"]["gametest"] == 1
    assert (data / "bedrock_server-1.26.52.3").is_file()
    pack = world / "behavior_packs/MonsterTruck_BP"
    manifest = json.loads((pack / "manifest.json").read_text())
    modules = {d.get("module_name"): d.get("version") for d in manifest["dependencies"]}
    assert modules["@minecraft/server-gametest"] == "1.0.0-beta"
    assert modules["@minecraft/server"] == "2.11.0-beta"
    assert manifest["modules"][-1]["entry"] == "scripts/scenario_entry.js"
    entry = (pack / "scripts/scenario_entry.js").read_text()
    assert 'import "./main.js"' in entry and 'import "./scenario_driver/main.js"' in entry
    assert "export const run" in (pack / "scripts/scenario_driver/run_config.js").read_text()
    production = json.loads((REPO_ROOT / "behavior_packs/MonsterTruck_BP/manifest.json").read_text())
    assert not any("gametest" in str(d) for d in production["dependencies"])
    assert {"module_name": "@minecraft/server", "version": "2.10.0"} in production["dependencies"]
    active = [entry["pack_id"] for entry in json.loads((world / "world_behavior_packs.json").read_text())]
    assert active == [production["header"]["uuid"]]


@pytest.mark.parametrize("archive_name", ["server_zip", "template_bytes"])
def test_an_unsafe_server_or_world_starter_archive_blocks_the_run(server_files, tmp_path, monkeypatch, archive_name):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zipped:
        zipped.writestr("bedrock_server", b"binary")
        zipped.writestr("../escaped.txt", "bad")
    replacement = (lambda root, server: bad) if archive_name == "server_zip" else (lambda root: bad.read_bytes())
    monkeypatch.setattr(scenarios, archive_name, replacement)
    with pytest.raises(scenarios.ScenarioError, match="Unsafe path"):
        scenarios.prepare_server(REPO_ROOT, server_files, RUN, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists() and not (tmp_path / "out/escaped.txt").exists()


class FakeDocker:
    def __init__(self, logs):
        self.logs = logs
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        out = {"logs": self.logs, "inspect": "true\n"}.get(args[0], "container-id\n")
        return subprocess.CompletedProcess(args, 0, out, "")


def test_container_is_isolated_stopped_and_removed_after_a_run(server_files, tmp_path):
    docker = FakeDocker(marker("PASS", scenario="smoke", checks=["spawned"]) + marker("DONE"))
    result = scenarios.run_scenarios(REPO_ROOT, server_files, RUN, tmp_path, run=docker, sleep=lambda _: None)
    assert result["status"] == "passed"
    start = docker.calls[0]
    assert start[:2] == ("run", "-d") and "-t" in start
    assert start[start.index("--network") + 1] == "none"
    assert start[-1] == server_files["scenario_server"]["image"]
    assert not any(arg.startswith("-p") or arg == "--publish" for arg in start)
    assert ("stop", "-t", "30", "monster-truck-scenario-" + RUN) in docker.calls
    assert docker.calls[-1] == ("rm", "monster-truck-scenario-" + RUN)
    assert not (tmp_path / "server").exists()
    assert "DONE" in (tmp_path / "scenario-server.log").read_text()


def test_container_is_removed_even_when_reading_logs_fails(server_files, tmp_path):
    docker = FakeDocker("")
    original = docker.__call__

    def failing(*args):
        if args[0] == "inspect":
            raise OSError("docker daemon went away")
        return original(*args)

    with pytest.raises(OSError):
        scenarios.run_scenarios(REPO_ROOT, server_files, RUN, tmp_path, run=failing, sleep=lambda _: None)
    assert docker.calls[-1] == ("rm", "monster-truck-scenario-" + RUN)


def test_only_narrows_scenarios_in_configured_order_and_rejects_unknown_names():
    config = {"scenario_server": {"scenarios": ["smoke", "seats", "handbrake"]}}
    assert scenarios.select_scenarios(config, "handbrake, smoke")["scenario_server"]["scenarios"] == ["smoke", "handbrake"]
    assert config["scenario_server"]["scenarios"] == ["smoke", "seats", "handbrake"], "the loaded config is not mutated"
    for bad in ("jump", "", "smoke,jump"):
        with pytest.raises(scenarios.ScenarioError, match="choose from: smoke, seats, handbrake"):
            scenarios.select_scenarios(config, bad)


def tmp_repo(tmp_path):
    """A tmp repo with this repo's config and pack manifests, so run reports are never written into the real repo."""
    root = tmp_path / "repo"
    config = json.loads((REPO_ROOT / "testing/bedrock.json").read_text())
    (root / "testing").mkdir(parents=True)
    (root / "testing/bedrock.json").write_text(json.dumps(config))
    for key in ("behavior_pack", "resource_pack"):
        (root / config[key]).mkdir(parents=True)
        (root / config[key] / "manifest.json").write_bytes((REPO_ROOT / config[key] / "manifest.json").read_bytes())
    return root


def test_a_failing_scenario_fails_the_run_with_exit_code_1(tmp_path, monkeypatch):
    # CI (.github/workflows/scenarios.yml) fails the job on this exit code.
    from scripts import bedrock_test
    root = tmp_repo(tmp_path)
    failed = {"status": "failed", "scenarios": {"trample": {"status": "failed", "checks": []}}, "errors": ["trample"]}
    monkeypatch.setattr(bedrock_test, "run_scenario_stage", lambda *a: failed)
    assert bedrock_test.main(["scenarios"], root=root) == 1
    report = json.loads((root / "dist/bedrock-tests/latest.json").read_text())
    assert report["status"] == "failed" and report["scenarios"] == failed


def test_reports_record_the_evidence_an_acceptance_record_needs(tmp_path, monkeypatch):
    # ADR-0018 / docs/ACCEPTANCE_COVERAGE.md "Evidence record": revision, working-tree state, versions.
    from scripts import bedrock_test
    root = tmp_repo(tmp_path)
    git = lambda *args: subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    (root / ".gitignore").write_text("dist/\n")  # as in this repo: run output never dirties the tree
    (root / "notes.txt").write_text("fixture\n")
    git("init", "-q")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture")
    passed = {"status": "passed", "scenarios": {}, "errors": []}
    monkeypatch.setattr(bedrock_test, "run_scenario_stage", lambda *a: passed)
    config = json.loads((root / "testing/bedrock.json").read_text())
    manifest = json.loads((root / config["behavior_pack"] / "manifest.json").read_text())

    assert bedrock_test.main(["scenarios"], root=root) == 0
    evidence = json.loads((root / "dist/bedrock-tests/latest.json").read_text())["evidence"]
    assert evidence == {
        "revision": git("rev-parse", "HEAD").stdout.strip(),
        "working_tree_clean": True,
        "changed_files": [],
        "addon_version": ".".join(map(str, manifest["header"]["version"])),
        "game_versions": {"linux_client": config["linux_client_version"],
                          "scenario_server": config["scenario_server"]["version"]},
    }

    (root / "testing/bedrock.json").write_text(json.dumps(config, indent=1))
    bedrock_test.main(["scenarios"], root=root)
    evidence = json.loads((root / "dist/bedrock-tests/latest.json").read_text())["evidence"]
    assert evidence["working_tree_clean"] is False
    assert evidence["changed_files"] == ["testing/bedrock.json"]

    git("mv", "notes.txt", "renamed.txt")  # a staged rename lists both real paths, not "a -> b"
    bedrock_test.main(["scenarios"], root=root)
    evidence = json.loads((root / "dist/bedrock-tests/latest.json").read_text())["evidence"]
    assert evidence["changed_files"] == ["notes.txt", "renamed.txt", "testing/bedrock.json"]


def test_an_unreadable_addon_version_does_not_break_a_run(tmp_path, monkeypatch):
    from scripts import bedrock_test
    root = tmp_repo(tmp_path)
    config = json.loads((root / "testing/bedrock.json").read_text())
    (root / config["behavior_pack"] / "manifest.json").write_text(json.dumps({"header": {}}))
    monkeypatch.setattr(bedrock_test, "run_scenario_stage", lambda *a: {"status": "passed", "scenarios": {}, "errors": []})
    assert bedrock_test.main(["scenarios"], root=root) == 0
    assert json.loads((root / "dist/bedrock-tests/latest.json").read_text())["evidence"]["addon_version"] is None


def test_reports_outside_a_git_checkout_say_the_revision_is_unknown(tmp_path, monkeypatch):
    from scripts import bedrock_test
    root = tmp_repo(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setattr(bedrock_test, "run_scenario_stage", lambda *a: {"status": "passed", "scenarios": {}, "errors": []})
    assert bedrock_test.main(["scenarios"], root=root) == 0
    evidence = json.loads((root / "dist/bedrock-tests/latest.json").read_text())["evidence"]
    assert evidence["revision"] is None and evidence["working_tree_clean"] is None


def test_only_is_rejected_outside_scenarios_mode(tmp_path):
    from scripts import bedrock_test
    root = tmp_repo(tmp_path)
    assert bedrock_test.main(["static", "--only", "smoke"], root=root) == 2
    report = json.loads((root / "dist/bedrock-tests/latest.json").read_text())
    assert report["error"] == "--only is only accepted by scenarios"
