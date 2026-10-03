"""Linux (flatpak mcpelauncher) client path of the Bedrock smoke runner."""
import signal
import subprocess

import pytest

from scripts import bedrock_client as clients
from scripts import bedrock_linux as linux
from scripts import bedrock_test as runner
from scripts import bedrock_world as world_setup


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    data = tmp_path / ".var/app/io.mrarm.mcpelauncher/data/mcpelauncher"
    account = data / "games/com.mojang"
    (account / "minecraftpe").mkdir(parents=True)
    (account / "minecraftpe/options.txt").write_text("content_log_file:0\n")
    (data / "versions/1.26.52.3/lib").mkdir(parents=True)
    for version in ("1.26.40.1", "1.26.45.1"):
        (data / "mods/mcpelauncher-updates" / version / "x86_64").mkdir(parents=True)
    return data, account


def test_account_and_logs_are_discovered_in_the_flatpak_data_directory(launcher, tmp_path):
    _, account = launcher
    assert world_setup.account_root() == account.resolve()
    logs = world_setup.enable_logging(tmp_path / "repo", account)
    assert logs == (account / "logs").resolve()
    assert (account / "minecraftpe/options.txt").read_text() == "content_log_file:1\n"


def test_launch_loads_world_with_pinned_version_and_newest_updates_mod(launcher, monkeypatch, tmp_path):
    data, _ = launcher
    calls = []
    monkeypatch.setattr(linux.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)) or "process")
    assert linux.launch("addon test=+", "1.26.52.3", tmp_path / "client.log") == "process"
    argv, kwargs = calls[0]
    assert argv[:4] == ["flatpak", "run", "--command=mcpelauncher-client", "io.mrarm.mcpelauncher"]
    assert argv[argv.index("-dg") + 1] == str(data / "versions/1.26.52.3")
    assert argv[argv.index("-u") + 1] == "minecraft://?load=addon%20test%3D%2B"
    assert argv[argv.index("-m") + 1] == str(data / "mods/mcpelauncher-updates/1.26.45.1/x86_64") + "/"
    assert kwargs["start_new_session"] is True


def test_launch_refuses_a_version_the_launcher_has_not_downloaded(launcher, tmp_path):
    with pytest.raises(linux.ClientError, match="1.26.99.1 is not downloaded"):
        linux.launch("world", "1.26.99.1", tmp_path / "client.log")


class Sandbox:
    """The launched process group: outer bwrap (the Popen'd leader), inner bwrap (sandbox init) and the game."""

    def __init__(self, monkeypatch, exits_on=("window close",)):
        self.members = [(4242, "bwrap"), (4250, "bwrap"), (4251, "MINECRAFT MAIN ")]
        self.events = []
        self.exits_on = exits_on
        self.clock = 0.0
        monkeypatch.setattr(linux, "process_group", lambda pgid: list(self.members) if pgid == 4242 else [])
        monkeypatch.setattr(linux, "run_kwin_script", lambda *a: self.event("window close"))
        monkeypatch.setattr(linux.os, "kill", lambda pid, sig: self.event((pid, sig)))
        monkeypatch.setattr(linux.os, "killpg", lambda *a: self.events.append(("killpg",) + a))
        monkeypatch.setattr(linux.time, "monotonic", lambda: self.clock)
        monkeypatch.setattr(linux.time, "sleep", self.sleep)

    def event(self, event):
        self.events.append(event)
        if event in self.exits_on:
            self.members = []

    def sleep(self, seconds):
        self.clock += seconds


class Launched:
    pid = 4242

    def poll(self):
        return None


def test_close_waits_for_the_whole_sandbox_after_a_normal_window_close(monkeypatch, tmp_path):
    sandbox = Sandbox(monkeypatch)
    linux.close(Launched(), tmp_path, timeout=1)
    assert sandbox.events == ["window close"]


def test_close_terminates_the_game_process_when_the_window_close_is_ignored(monkeypatch, tmp_path):
    # SIGTERM to the group ended only the outer bwrap: the inner bwrap is the sandbox's PID-namespace
    # init and ignores it, so the game kept running while close() reported success.
    sandbox = Sandbox(monkeypatch, exits_on=[(4251, signal.SIGTERM)])
    linux.close(Launched(), tmp_path, timeout=1)
    assert sandbox.events == ["window close", (4251, signal.SIGTERM)]


def test_close_still_closes_the_sandbox_after_the_launched_leader_exited(monkeypatch, tmp_path):
    sandbox = Sandbox(monkeypatch)

    class Exited(Launched):
        def poll(self):
            return 0

    linux.close(Exited(), tmp_path, timeout=1)
    assert sandbox.events == ["window close"]


def test_close_reports_a_game_that_survives_sigterm_and_never_force_stops_it(monkeypatch, tmp_path):
    sandbox = Sandbox(monkeypatch, exits_on=())
    with pytest.raises(linux.ClientError, match=r"no process was force-stopped.*4251"):
        linux.close(Launched(), tmp_path, timeout=1)
    assert sandbox.events == ["window close", (4251, signal.SIGTERM)]


def test_close_does_nothing_when_the_sandbox_is_already_gone(monkeypatch, tmp_path):
    sandbox = Sandbox(monkeypatch)
    sandbox.members = []
    linux.close(Launched(), tmp_path, timeout=1)
    linux.close(None, tmp_path, timeout=1)
    assert sandbox.events == []


def test_process_group_lists_live_members_with_names_containing_spaces():
    child = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        assert linux.process_group(child.pid) == [(child.pid, "sleep")]
    finally:
        child.kill()
        child.wait()
    assert linux.process_group(child.pid) == []


def test_running_client_blocks_deployment(monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, "com.bitwarden.desktop\nio.mrarm.mcpelauncher\n", ""))
    with pytest.raises(runner.SetupError, match="Close Minecraft"):
        clients.LauncherClient().assert_closed()


def test_unlistable_flatpak_blocks_deployment(monkeypatch):
    monkeypatch.setattr(linux.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no session bus"))
    with pytest.raises(runner.SetupError, match="flatpak ps failed: no session bus"):
        clients.LauncherClient().assert_closed()


class FakeClient:
    returncode = None

    def poll(self):
        return None


class FakeLauncher:
    """Stands in for bedrock_linux: no flatpak, KWin or spectacle; launch is supplied per test."""
    ClientError = linux.ClientError

    def __init__(self, launch=None):
        self.calls = []
        self.launch_fn = launch

    def client_running(self):
        return False

    def launch(self, name, version, log_path):
        self.calls.append(("launch", name, version, log_path.name))
        return self.launch_fn(log_path)

    def capture(self, directory):
        return "fixture.png"

    def close(self, client, output):
        self.calls.append(("close", type(client).__name__))


@pytest.fixture
def linux_project(launcher, tmp_path):
    root = tmp_path / "repo"
    config = {
        "name": "Fixture", "entity_id": "fixture:vehicle", "behavior_pack": "bp", "resource_pack": "rp",
        "harness_uuid": "b06f3b8a-1a26-4f26-a3aa-76c2c480ad35",
        "harness_module_uuid": "acf83677-0a76-42e8-bf6e-d84993212967",
        "script_api_version": "2.10.0", "linux_client_version": "1.26.52.3",
        "timeout_seconds": 2, "settle_seconds": 0,
    }
    for name, pack_id in (("bp", "e66fb143-6f34-4b80-aa0d-94984cce62dd"), ("rp", "7d5ae6fc-64b4-4d29-8f73-8dc81d43b76e")):
        runner.write_json(root / name / "manifest.json",
                          {"header": {"uuid": pack_id, "version": [1, 0, 0], "min_engine_version": [1, 26, 40]}})
    (root / "testing/harness").mkdir(parents=True)
    (root / "testing/harness/main.js").write_text("// fixture")
    _, account = launcher
    world = account / "minecraftWorlds/dedicated"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"fixture world")
    logs = world_setup.enable_logging(root, account)
    world_setup.configure(root, config, world, logs, clients.LauncherClient(launcher=FakeLauncher()))
    (tmp_path / "out").mkdir()
    return root, config, world


def client_output(world, pack_ids):
    lines = ["Info  [Minecraft] NO LOG FILE! - Opening level '%s'" % (world / "db")]
    lines += ["Info  [Minecraft] NO LOG FILE! - Pack Stack - [%02d] Pack (id: %s, version: 1.0.0)" % (index, pack_id)
              for index, pack_id in enumerate(pack_ids)]
    lines.append("Info  [Minecraft] NO LOG FILE! - Player Spawned: fixture xuid: 1")
    return "\n".join(lines) + "\n"


def test_linux_game_run_passes_on_world_load_and_marks_gameplay_unverified(linux_project, tmp_path):
    root, config, world = linux_project

    def launch(log_path):
        log_path.write_text(client_output(world, [world_setup.dedicated_pack_ids(config)[0], config["harness_uuid"]]))
        return FakeClient()

    launcher = FakeLauncher(launch)
    result = runner.run_game(root, config, "fresh", tmp_path / "out", client=clients.LauncherClient(launcher=launcher))
    assert result["status"] == "passed"
    assert result["stages"]["world_load"]["status"] == "passed"
    assert result["stages"]["gameplay"]["status"] == "not_verified"
    assert launcher.calls == [("launch", "dedicated", "1.26.52.3", "client-stdout.log"), ("close", "FakeClient")]


def test_linux_game_run_fails_when_a_deployed_pack_is_not_loaded(linux_project, tmp_path):
    root, config, world = linux_project

    def launch(log_path):
        log_path.write_text(client_output(world, [config["harness_uuid"]]))
        return FakeClient()

    result = runner.run_game(root, config, "fresh", tmp_path / "out",
                             client=clients.LauncherClient(launcher=FakeLauncher(launch)))
    assert result["status"] == "failed"
    assert result["stages"]["world_load"]["status"] == "failed"
    assert any("missing pack " + world_setup.dedicated_pack_ids(config)[0] in error for error in result["errors"])
