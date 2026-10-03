"""Headless Scenario Runs on a disposable Bedrock Dedicated Server container (ADR-0016)."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile

try:
    from .bedrock_world import customize_level, template_bytes
except ImportError:
    from bedrock_world import customize_level, template_bytes


MARKER = "[SCENARIO]"
LEVEL = "Scenario World"


class ScenarioError(Exception):
    pass


def docker(*args):
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, errors="replace", timeout=120)
    except FileNotFoundError as error:
        raise ScenarioError("Docker is required for Scenario Runs") from error


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def server_zip(root, server):
    """The pinned official server archive, downloaded once and verified on every use."""
    cached = root / "dist/bedrock-tests/cache" / f"bedrock-server-{server['version']}.zip"
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(".partial")
        request = urllib.request.Request(server["url"], headers={"User-Agent": "monster-truck-scenario-runner"})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        partial.rename(cached)
    digest = hashlib.sha256()
    with cached.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != server["sha256"]:
        raise ScenarioError(f"Server archive SHA-256 mismatch for {cached}; delete it to re-download")
    return cached


def prepare_server(root, config, run_id, output):
    """Unpack the server and build the Scenario World with a test copy of the add-on running the scenario driver."""
    server = config["scenario_server"]
    data = output / "server"
    with zipfile.ZipFile(server_zip(root, server)) as archive:
        for item in archive.infolist():
            path = Path(item.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ScenarioError("Unsafe path in server archive")
        archive.extractall(data)
    binary = data / f"bedrock_server-{server['version']}"
    (data / "bedrock_server").rename(binary)
    binary.chmod(0o755)

    world = data / "worlds" / LEVEL
    with zipfile.ZipFile(io.BytesIO(template_bytes(root))) as archive:
        for item in archive.infolist():
            path = Path(item.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                raise ScenarioError("Unsafe path in world starter")
        archive.extractall(world)
    (world / "level.dat").write_bytes(customize_level((world / "level.dat").read_bytes(), LEVEL, beta_apis=True))
    (world / "levelname.txt").write_text(LEVEL, encoding="utf-8")

    bp = json.loads((root / config["behavior_pack"] / "manifest.json").read_text(encoding="utf-8"))
    rp = json.loads((root / config["resource_pack"] / "manifest.json").read_text(encoding="utf-8"))
    pack = world / "behavior_packs/MonsterTruck_BP"
    shutil.copytree(root / config["behavior_pack"], pack)
    shutil.copytree(root / config["resource_pack"], world / "resource_packs/MonsterTruck_RP")
    # A Simulated Driver only exists as a player object in the script runtime that spawned it,
    # so the scenario driver runs inside this test copy of the add-on's runtime (ADR-0016).
    shutil.copytree(root / "testing/scenarios", pack / "scripts/scenario_driver")
    (pack / "scripts/scenario_entry.js").write_text(
        'import "./main.js";\nimport "./scenario_driver/main.js";\n', encoding="utf-8")
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    for module in manifest["modules"]:
        if module["type"] == "script":
            module["entry"] = "scripts/scenario_entry.js"
    manifest["dependencies"] = [dependency for dependency in manifest["dependencies"]
                                if dependency.get("module_name") != "@minecraft/server"] + [
        {"module_name": "@minecraft/server", "version": server["server_api_version"]},
        {"module_name": "@minecraft/server-gametest", "version": server["gametest_api_version"]},
    ]
    write_json(pack / "manifest.json", manifest)
    run = {"run_id": run_id, "entity_id": config["entity_id"], "scenarios": server["scenarios"]}
    (pack / "scripts/scenario_driver/run_config.js").write_text(
        "export const run = " + json.dumps(run) + ";\n", encoding="utf-8")
    write_json(world / "world_behavior_packs.json", [
        {"pack_id": bp["header"]["uuid"], "version": bp["header"]["version"]},
    ])
    write_json(world / "world_resource_packs.json", [
        {"pack_id": rp["header"]["uuid"], "version": rp["header"]["version"]},
    ])
    return data


def parse_markers(text, run_id):
    markers = []
    for line in text.splitlines():
        if MARKER not in line:
            continue
        try:
            marker, _ = json.JSONDecoder().raw_decode(line.split(MARKER, 1)[1].lstrip())
        except ValueError:
            continue
        if isinstance(marker, dict) and marker.get("run_id") == run_id:
            markers.append(marker)
    return markers


def evaluate(text, run_id, scenarios):
    markers = parse_markers(text, run_id)
    results = {name: {"status": "not_run"} for name in scenarios}
    errors = []
    for marker in markers:
        name = marker.get("scenario")
        if marker["status"] == "PASS" and name in results:
            results[name] = {"status": "passed", "checks": marker.get("checks", [])}
        elif marker["status"] == "FAIL":
            results.setdefault(name, {})
            results[name] = {"status": "failed", "error": marker.get("error", "unspecified failure")}
            errors.append(f"{name}: {results[name]['error']}")
    for name, result in results.items():
        if result["status"] == "not_run":
            errors.append(f"{name}: no result reported")
    # Any other server warning or error (content log, pack, script) fails the run.
    for line in text.splitlines():
        if MARKER not in line and re.search(r"\b(?:WARN|ERROR)\]", line):
            errors.append(line.strip())
    done = any(marker["status"] == "DONE" for marker in markers)
    return {"status": "passed" if done and not errors else "failed", "scenarios": results,
            "errors": errors, "done": done}


def select_scenarios(config, only):
    """Return a config copy that runs only the named scenarios, in configured order."""
    names = [name.strip() for name in only.split(",") if name.strip()]
    configured = config["scenario_server"]["scenarios"]
    unknown = [name for name in names if name not in configured]
    if not names or unknown:
        raise ScenarioError(f"Unknown scenario(s) {unknown or only!r}; choose from: {', '.join(configured)}")
    return {**config, "scenario_server": {**config["scenario_server"],
                                          "scenarios": [name for name in configured if name in names]}}


def run_scenarios(root, config, run_id, output, run=docker, clock=time.monotonic, sleep=time.sleep):
    server = config["scenario_server"]
    name = "monster-truck-scenario-" + run_id
    data = prepare_server(root, config, run_id, output)
    # A TTY keeps the server's stdout line-buffered so markers are visible while it runs.
    started = run("run", "-d", "-t", "--name", name, "--network", "none",
                  "-e", "EULA=TRUE", "-e", "VERSION=EXISTING", "-e", f"LEVEL_NAME={LEVEL}",
                  "-e", "GAMEMODE=creative", "-e", "ALLOW_CHEATS=true", "-e", "ONLINE_MODE=false",
                  "-e", "ALLOW_LIST=false",
                  "-e", "CONTENT_LOG_CONSOLE_OUTPUT_ENABLED=true",
                  "-e", f"UID={os.getuid()}", "-e", f"GID={os.getgid()}",
                  "-v", f"{data}:/data", server["image"])
    if started.returncode:
        shutil.rmtree(data, ignore_errors=True)
        raise ScenarioError("Could not start the scenario server container: " + started.stderr.strip())
    text = ""
    try:
        deadline = clock() + server["timeout_seconds"]
        while clock() < deadline:
            logs = run("logs", name)
            text = logs.stdout + logs.stderr
            if any(marker["status"] == "DONE" for marker in parse_markers(text, run_id)):
                break
            if "Quit correctly" in text:
                break
            state = run("inspect", "-f", "{{.State.Running}}", name)
            if state.stdout.strip() != "true":
                break
            sleep(1)
    finally:
        run("stop", "-t", "30", name)
        logs = run("logs", name)
        text = logs.stdout + logs.stderr or text
        (output / "scenario-server.log").write_text(text, encoding="utf-8")
        run("rm", name)
        shutil.rmtree(data, ignore_errors=True)
    result = evaluate(text, run_id, server["scenarios"])
    if not result["done"]:
        result["errors"].append("Scenario server stopped or timed out before reporting DONE")
    return result
