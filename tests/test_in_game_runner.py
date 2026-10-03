import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import bedrock_client as clients
from scripts import bedrock_test as runner
from scripts import bedrock_world as worlds


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Never reach the real Linux desktop or launcher data; clients are injected as FakeClient."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


class FakeClient(clients.WindowsClient):
    """Windows verdict rules (a fresh content-log marker) with the desktop replaced by recorded calls."""

    def __init__(self, on_launch=None, verdict=None, capture=None, close=None):
        super().__init__(running=lambda: False)
        self.calls = []
        self.on_launch, self.verdict, self.capture_fn, self.close_fn = on_launch, verdict, capture, close

    def open_uri(self, uri):
        self.calls.append(uri)
        if self.on_launch:
            self.on_launch()

    def await_verdict(self, config, run_id, output, on_poll=None):
        if self.verdict:
            return self.verdict(on_poll=on_poll)
        return super().await_verdict(config, run_id, output, on_poll=on_poll)

    def capture(self, directory):
        return self.capture_fn(directory) if self.capture_fn else "fixture.png"

    def close(self, output):
        self.calls.append("closed")
        if self.close_fn:
            self.close_fn()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = tmp_path / "repo"
    config = {
        "name": "Fixture", "entity_id": "fixture:vehicle",
        "behavior_pack": "bp", "resource_pack": "rp",
        "harness_uuid": "b06f3b8a-1a26-4f26-a3aa-76c2c480ad35",
        "harness_module_uuid": "acf83677-0a76-42e8-bf6e-d84993212967",
        "script_api_version": "2.0.0", "required_components": [],
        "timeout_seconds": 2, "settle_seconds": 0.5,
        "static_timeout_seconds": 5,
        "static_commands": [["{python}", "-c", "print('static fixture passed')"]],
    }
    for name, pack_id in (("bp", "e66fb143-6f34-4b80-aa0d-94984cce62dd"),
                          ("rp", "7d5ae6fc-64b4-4d29-8f73-8dc81d43b76e")):
        runner.write_json(root / name / "manifest.json", {
            "header": {"uuid": pack_id, "version": [1, 0, 0], "min_engine_version": [1, 26, 40]},
        })
    runner.write_json(root / "testing/bedrock.json", config)
    (root / "testing/harness").mkdir()
    (root / "testing/harness/main.js").write_text("// fixture")
    world = tmp_path / "minecraftWorlds/dedicated"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"fixture world")
    options = tmp_path / "minecraftpe/options.txt"
    options.parent.mkdir()
    options.write_text("content_log_file:1\n")
    logs = tmp_path / "Minecraft Bedrock/logs"
    logs.mkdir(parents=True)
    return root, config, world, logs


def marker(run_id="fresh", status="PASS", **extra):
    data = {"run_id": run_id, "entity_id": "fixture:vehicle", "status": status,
            "checks": ["spawned fixture:vehicle"], **extra}
    return "[Scripting][warning]-" + clients.MARKER + json.dumps(data) + "\n"


def test_log_reader_ignores_history_and_reassembles_partial_lines(tmp_path):
    path = tmp_path / "ContentLog.log"
    path.write_text(marker("old"))
    logs = clients.FreshLogs(tmp_path)
    assert logs.read() == []
    fresh = marker()
    with path.open("a") as stream:
        stream.write(fresh[:20])
    assert logs.read() == []
    with path.open("a") as stream:
        stream.write(fresh[20:])
    errors, warnings, passes = clients.evaluate_lines(logs.read(), "fresh", "fixture:vehicle")
    assert not errors and not warnings
    assert passes[0]["run_id"] == "fresh"


def test_log_reader_handles_new_files_and_truncation(tmp_path):
    old = tmp_path / "old.log"
    old.write_text("old history\n" * 100)
    logs = clients.FreshLogs(tmp_path)
    old.write_text("[ERROR] truncated\n")
    (tmp_path / "new.log").write_text(marker())
    lines = logs.read()
    assert any("truncated" in line for _, line in lines)
    assert any("fresh" in line for _, line in lines)


@pytest.mark.parametrize("line", [
    "[ERROR] " + clients.MARKER + "broken JSON",
    marker("another-run"), marker(checks=[]), marker(entity_id="wrong:entity"),
    "[ERROR] " + marker(), marker(status="FAIL", error="cannot spawn"),
])
def test_invalid_or_failed_markers_cannot_pass(line):
    errors, _, passes = clients.evaluate_lines([("log", line)], "fresh", "fixture:vehicle")
    assert errors and not passes


class FakeClock:
    now = 0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_missing_logs_timeout_instead_of_passing(project, tmp_path):
    _, config, _, logs = project
    clock = FakeClock()
    result = clients.await_result(clients.FreshLogs(logs), config, "fresh", tmp_path,
                                 clock.clock, clock.sleep)
    assert result["status"] == "failed"
    assert "Timed out" in result["errors"][0]


def test_fresh_pass_requires_clean_settling_period(project, tmp_path):
    _, config, _, logs = project
    reader = clients.FreshLogs(logs)
    (logs / "content.log").write_text(marker())
    clock = FakeClock()
    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, clock.sleep)
    assert result["status"] == "passed"
    assert clock.now >= config["settle_seconds"]


def test_showcase_observation_continues_after_early_pass(project, tmp_path):
    _, config, _, logs = project
    config["observe_seconds"] = 1.5
    reader = clients.FreshLogs(logs)
    (logs / "content.log").write_text(marker())
    clock = FakeClock()
    observations = []
    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, clock.sleep,
                                 on_poll=lambda: observations.append(clock.now))
    assert result["status"] == "passed"
    assert observations[-1] >= 1.5


def test_warning_after_pass_fails(project, tmp_path):
    _, config, _, logs = project
    reader = clients.FreshLogs(logs)
    path = logs / "content.log"
    path.write_text(marker())
    clock = FakeClock()

    def sleep(seconds):
        clock.sleep(seconds)
        with path.open("a") as stream:
            stream.write("[Rendering][warning]-Missing texture\n")

    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, sleep)
    assert result["status"] == "failed"
    assert result["warnings"]


def test_unfinished_log_line_after_pass_cannot_be_ignored(project, tmp_path):
    _, config, _, logs = project
    reader = clients.FreshLogs(logs)
    (logs / "content.log").write_text(marker() + "[ERROR] partial write")
    clock = FakeClock()
    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, clock.sleep)
    assert result["status"] == "failed"


@pytest.mark.parametrize("error_line", ["", "[Sound][error]-invalid sound schema\n"])
def test_shutdown_flush_supplies_real_result_and_retains_errors(project, tmp_path, error_line):
    _, config, _, logs = project
    reader = clients.FreshLogs(logs)
    clock = FakeClock()
    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, clock.sleep)
    assert result["status"] == "failed"
    (logs / "content.log").write_text(error_line + marker())
    result = clients.finalize_game_logs(reader, result, config, "fresh", tmp_path)
    assert result["status"] == ("failed" if error_line else "passed")
    assert result["marker"]["run_id"] == "fresh"
    assert bool(result["errors"]) == bool(error_line)
    assert marker().strip() in (tmp_path / "content.log").read_text()


def test_shutdown_without_runtime_result_still_fails(project, tmp_path):
    _, config, _, logs = project
    reader = clients.FreshLogs(logs)
    clock = FakeClock()
    result = clients.await_result(reader, config, "fresh", tmp_path, clock.clock, clock.sleep)
    assert clients.finalize_game_logs(reader, result, config, "fresh", tmp_path)["status"] == "failed"


def test_configure_and_redeploy_are_confined_to_owned_world(project):
    root, config, world, logs = project
    worlds.configure(root, config, world, logs, FakeClient())
    original_level = (world / "level.dat").read_bytes()
    untouched = world / "behavior_packs/unrelated/keep.txt"
    untouched.parent.mkdir(parents=True)
    untouched.write_text("preserve")
    worlds.deploy(root, config, world, "fresh")
    deployed_bp = world / f"behavior_packs/addon-test-{config['harness_uuid']}"
    deployed_rp = world / f"resource_packs/addon-test-{config['harness_uuid']}"
    source_bp_id = runner.read_json(root / "bp/manifest.json")["header"]["uuid"]
    source_rp_id = runner.read_json(root / "rp/manifest.json")["header"]["uuid"]
    deployed_bp_id = runner.read_json(deployed_bp / "manifest.json")["header"]["uuid"]
    deployed_rp_id = runner.read_json(deployed_rp / "manifest.json")["header"]["uuid"]
    assert deployed_bp_id != source_bp_id
    assert deployed_rp_id != source_rp_id
    assert runner.read_json(world / "world_behavior_packs.json")[0]["pack_id"] == deployed_bp_id
    assert runner.read_json(world / "world_resource_packs.json")[0]["pack_id"] == deployed_rp_id
    generated = world / f"behavior_packs/addon-harness-{config['harness_uuid']}/scripts/run_config.js"
    assert '"run_id": "fresh"' in generated.read_text()
    assert untouched.read_text() == "preserve"
    assert (world / "level.dat").read_bytes() == original_level
    assert not (root / "bp/scripts").exists()


def test_refuses_world_with_existing_active_packs(project):
    root, config, world, logs = project
    runner.write_json(world / "world_behavior_packs.json", [{"pack_id": "unrelated"}])
    with pytest.raises(runner.SetupError, match="fresh dedicated"):
        worlds.configure(root, config, world, logs, FakeClient())
    assert not (world / worlds.OWNER).exists()


def test_configure_refuses_while_minecraft_runs(project):
    root, config, world, logs = project
    with pytest.raises(runner.SetupError, match="Close Minecraft"):
        worlds.configure(root, config, world, logs, clients.WindowsClient(running=lambda: True))
    assert not (world / worlds.OWNER).exists()


def test_refuses_unrelated_packs_added_after_configuration(project):
    root, config, world, logs = project
    worlds.configure(root, config, world, logs, FakeClient())
    runner.write_json(world / "world_behavior_packs.json", [{"pack_id": "unrelated"}])
    with pytest.raises(runner.SetupError, match="unrelated active packs"):
        worlds.deploy(root, config, world, "fresh")
    assert runner.read_json(world / "world_behavior_packs.json") == [{"pack_id": "unrelated"}]


def test_refuses_unowned_world(project):
    root, config, world, _ = project
    with pytest.raises(runner.SetupError, match="ownership"):
        worlds.deploy(root, config, world, "fresh")
    assert not (world / "behavior_packs").exists()


def test_rejects_redirected_metadata_before_writing(project, monkeypatch):
    root, config, world, logs = project
    metadata = world / "world_behavior_packs.json"
    original = Path.resolve

    def redirected(path, *args, **kwargs):
        if path == metadata:
            return root / "outside.json"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(runner.SetupError, match="redirected"):
        worlds.configure(root, config, world, logs, FakeClient())
    assert not (world / worlds.OWNER).exists()


def test_static_failure_stops_before_game_and_preserves_exit_code(project, monkeypatch):
    root, config, _, _ = project
    config["static_commands"] = [["{python}", "-c", "raise SystemExit(7)"]]
    runner.write_json(root / "testing/bedrock.json", config)
    monkeypatch.setattr(runner, "run_game", lambda *args: pytest.fail("game must not launch"))
    assert runner.main(["all"], root=root) == 1
    report = runner.read_json(root / "dist/bedrock-tests/latest.json")
    assert report["static"]["commands"][0]["exit_code"] == 7
    assert report["status"] == "failed"


def test_all_reports_blocked_when_automatic_setup_has_no_account(project, monkeypatch):
    root, _, _, _ = project
    assert runner.main(["all"], root=root, client=FakeClient()) == 2
    report = runner.read_json(root / "dist/bedrock-tests/latest.json")
    assert report["static"]["status"] == "passed"
    assert report["status"] == "blocked"
    assert "one initialized Minecraft account" in report["error"]


def test_legacy_dry_run_is_read_only_discovery(project, tmp_path):
    # A copy of scripts/ in the fixture repo: the entry point's own ROOT, and every discovered
    # install path, stay under tmp_path instead of the real repository and the user's game data.
    root, _, world, _ = project
    shutil.copytree(Path(__file__).resolve().parents[1] / "scripts", root / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "HOME": str(tmp_path / "home"), "APPDATA": str(tmp_path), "LOCALAPPDATA": str(tmp_path)}
    before = sorted(path for path in tmp_path.rglob("*") if "dist" not in path.parts)
    result = subprocess.run([sys.executable, "scripts/test_in_game.py", "--dry-run"], cwd=root,
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert "DIAGNOSTIC" in result.stdout
    assert "PASSED" not in result.stdout
    assert sorted(path for path in tmp_path.rglob("*") if "dist" not in path.parts and "__pycache__" not in path.parts) \
        == [path for path in before if "__pycache__" not in path.parts]
    assert runner.read_json(root / "dist/bedrock-tests/latest.json")["mode"] == "doctor"


def test_game_launches_encoded_world_requires_fresh_marker_and_closes(project, tmp_path):
    root, config, world, logs = project
    renamed = world.with_name("test world=+")
    world.rename(renamed)
    client = FakeClient(on_launch=lambda: (logs / "fresh.log").write_text(marker()))
    worlds.configure(root, config, renamed, logs, client)
    config["settle_seconds"] = 0
    result = runner.run_game(root, config, "fresh", tmp_path, client=client)
    assert result["status"] == "passed"
    assert result["stages"]["gameplay"] == {"status": "passed", "checks": ["spawned fixture:vehicle"]}
    assert "world_load" not in result["stages"]
    assert client.calls == ["minecraft://?load=test%20world%3D%2B", "closed"]


def test_game_closes_launched_client_when_log_read_fails(project, tmp_path):
    root, config, world, logs = project

    def fail(**kwargs):
        raise OSError("log unavailable")

    client = FakeClient(verdict=fail)
    worlds.configure(root, config, world, logs, client)
    with pytest.raises(OSError, match="log unavailable"):
        runner.run_game(root, config, "fresh", tmp_path, client=client)
    assert client.calls == ["minecraft://?load=dedicated", "closed"]


def test_windows_client_blocks_deployment_while_minecraft_runs():
    with pytest.raises(runner.SetupError, match="Close Minecraft"):
        clients.WindowsClient(running=lambda: True).assert_closed()


def window_port(windows, **calls):
    """A user32 port whose EnumWindows visits (hwnd, title, visible) in order."""
    from types import SimpleNamespace
    titles = {hwnd: (title, visible) for hwnd, title, visible in windows}

    def enum_windows(visit):
        for hwnd, _, _ in windows:
            if not visit(hwnd, 0):
                break

    def get_window_text(hwnd, buffer, size):
        buffer.value = titles[hwnd][0][:size - 1]
        return len(buffer.value)

    return SimpleNamespace(enum_windows=enum_windows, GetWindowTextW=get_window_text,
                           IsWindowVisible=lambda hwnd: titles[hwnd][1], **calls)


@pytest.mark.parametrize("windows,expected", [
    ([(1, "Minecraft", False), (2, "Minecraft Launcher", True), (3, "Minecraft for Windows", True)], 3),
    ([(4, "Notes", True), (5, "Minecraft", True)], 5),
    ([(6, "Minecraft", False), (7, "Minecraft Launcher", True)], None),
])
def test_game_window_is_the_visible_minecraft_titled_window(windows, expected):
    assert clients.find_game_window(window_port(windows)) == expected


def test_windows_close_posts_a_normal_close_to_the_game_window(tmp_path):
    posted = []
    post = lambda *message: posted.append(message) or True
    user32 = window_port([(7, "Minecraft Launcher", True), (42, "Minecraft", True)], PostMessageW=post)
    running = iter([True, False])
    clients.WindowsClient(user32=user32, running=lambda: next(running)).close(tmp_path)
    assert posted == [(42, 0x0010, 0, 0)]  # WM_CLOSE, no forced termination
    user32 = window_port([(42, "Minecraft", False)], PostMessageW=post)
    with pytest.raises(runner.SetupError, match="no closeable window"):
        clients.WindowsClient(user32=user32, running=lambda: True).close(tmp_path)
    assert len(posted) == 1


def test_capture_timeout_retains_last_stage(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("capture", 20, stderr=b"capture stage: grab_pixels\n")
    monkeypatch.setattr(clients.subprocess, "run", timeout)
    with pytest.raises(runner.SetupError, match="grab_pixels"):
        clients.WindowsClient().capture(tmp_path)


def test_capture_helper_must_produce_a_file(monkeypatch, tmp_path):
    monkeypatch.setattr(clients.subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess([], 0, str(tmp_path / "missing.png"), ""))
    with pytest.raises(runner.SetupError, match="no capture file"):
        clients.WindowsClient().capture(tmp_path)


@pytest.mark.parametrize("mode", ["window", "uniform", "fallback", "lost_focus"])
def test_capture_targets_window_and_guards_fallback(monkeypatch, tmp_path, mode):
    from types import SimpleNamespace
    from PIL import Image, ImageGrab
    def client_rect(hwnd, rect):
        rect._obj.right = 4
        rect._obj.bottom = 4
        return True
    foreground = iter([42, 42, 0 if mode == "lost_focus" else 42])
    user32 = window_port([(42, "Minecraft", True)], SetProcessDPIAware=lambda: True,
                         IsIconic=lambda hwnd: False, GetClientRect=client_rect,
                         GetForegroundWindow=lambda: next(foreground) if mode in ("fallback", "lost_focus") else 0,
                         ClientToScreen=lambda *a: True,
                         ShowWindowAsync=lambda *a: None, SetForegroundWindow=lambda *a: None)
    image = Image.new("RGB", (4, 4))
    if mode == "window":
        image.putpixel((0, 0), (255, 0, 0))
    def grab(*, window=None, bbox=None):
        if window is not None:
            assert window == 42
        else:
            assert bbox == (0, 0, 4, 4)
            image.putpixel((0, 0), (255, 0, 0))
        return image
    monkeypatch.setattr(ImageGrab, "grab", grab)
    if mode in ("uniform", "lost_focus"):
        with pytest.raises(runner.SetupError, match="[Ee]mpty or uniform|lost foreground"):
            clients._capture_game(tmp_path, user32=user32)
        assert not (tmp_path / "minecraft.png").exists()
    else:
        assert Path(clients._capture_game(tmp_path, user32=user32)).is_file()


@pytest.mark.parametrize("required,successes", [(False, 0), (True, 0), (True, 1), (True, 2)])
def test_capture_failure_preserves_gameplay_and_each_attempt(project, monkeypatch, tmp_path, required, successes):
    root, config, world, logs = project
    worlds.configure(root, config, world, logs, FakeClient())
    config["showcase"] = required
    ticks = iter(range(0, 200, 16))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))

    def await_pass(*args, **kwargs):
        kwargs["on_poll"]()
        kwargs["on_poll"]()
        return {"status": "passed", "errors": [], "warnings": [],
                "marker": json.loads(marker().split(clients.MARKER)[1])}

    captured = []
    def fail_capture(directory):
        if len(captured) < successes:
            captured.append(str(directory / "minecraft.png"))
            return captured[-1]
        raise runner.SetupError("capture stage: grab_pixels timed out")
    client = FakeClient(verdict=await_pass, capture=fail_capture)
    result = runner.run_game(root, config, "fresh", tmp_path, client=client)
    assert result["status"] == ("failed" if required and successes < 2 else "passed")
    assert result["stages"]["gameplay"]["status"] == "passed"
    assert result["stages"]["content_logs"]["status"] == "passed"
    assert result["stages"]["shutdown"]["status"] == "passed"
    captures = result["stages"]["screenshots"]
    assert captures["status"] == ("passed" if successes >= 2 else "failed")
    assert captures["required"] is required
    assert len(captures["attempts"]) == (3 if required else 1)
    failures = [attempt for attempt in captures["attempts"] if attempt["status"] == "failed"]
    assert all("grab_pixels" in attempt["error"] for attempt in failures)
    assert len(failures) == len(captures["attempts"]) - successes
    assert result["coverage"]["player_input"] == "not_verified"


def test_shutdown_failure_keeps_gameplay_evidence(project, tmp_path):
    root, config, world, logs = project
    config["settle_seconds"] = 0
    def fail_close():
        raise runner.SetupError("client did not close")
    client = FakeClient(on_launch=lambda: (logs / "fresh.log").write_text(marker()), close=fail_close)
    worlds.configure(root, config, world, logs, client)
    result = runner.run_game(root, config, "fresh", tmp_path, client=client)
    assert result["status"] == "failed"
    assert result["marker"]["status"] == "PASS"
    assert result["stages"]["shutdown"]["status"] == "failed"
    assert "client did not close" in result["errors"]


@pytest.mark.skipif(not shutil.which("node"), reason="Node is optional for offline JavaScript harness checks")
def test_javascript_assertions_cleanup_and_reject_wrong_seats():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const source = readFileSync(process.argv[1], 'utf8').replace(/^import .* from "@minecraft\/server";\r?\n/m, '');
const { assertAddon } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
let removed = 0;
let seats = 2;
const entity = { typeId: 'fixture:vehicle', remove() { removed++; },
  getComponent(name) { return name === 'minecraft:rideable' ? { seatCount: seats } : {}; } };
const player = { location: { x: 0, y: 4, z: 0 }, dimension: { spawnEntity() { return entity; } } };
const run = { entity_id: entity.typeId, required_components: ['minecraft:health'], expected_seat_count: 2 };
const result = await assertAddon(player, run);
assert.equal(removed, 0);
assert.ok(result.checks.includes('seat count 2'));
result.cleanup();
assert.equal(removed, 1);
seats = 1;
await assert.rejects(async () => assertAddon(player, run), /Unexpected seat count/);
assert.equal(removed, 2);
entity.typeId = 'wrong:entity';
await assert.rejects(async () => assertAddon(player, run), /identifier mismatch/);
assert.equal(removed, 3);
'''
    result = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script,
                             str(root / "testing/harness/assertions.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
