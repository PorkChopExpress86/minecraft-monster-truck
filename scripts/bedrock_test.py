"""Repository-owned Bedrock smoke runner (Windows and Linux). See docs/WINDOWS_TESTING.md and docs/LINUX_TESTING.md."""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

if __package__:
    from .addon_packs import com_mojang_roots, read_json, write_json
    from .bedrock_client import client_for_platform
    from .bedrock_world import SetupError, bootstrap, configure, deploy
else:
    from addon_packs import com_mojang_roots, read_json, write_json
    from bedrock_client import client_for_platform
    from bedrock_world import SetupError, bootstrap, configure, deploy


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"


def load_config(root):
    config = read_json(root / "testing/bedrock.json")
    for key in ("harness_uuid", "harness_module_uuid"):
        uuid.UUID(config[key])
    for key in ("behavior_pack", "resource_pack"):
        pack = (root / config[key]).resolve()
        if not pack.is_relative_to(root.resolve()) or not (pack / "manifest.json").is_file():
            raise SetupError(f"{key} must name a pack inside this repository")
    if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_.-]+", config["entity_id"]):
        raise SetupError("entity_id must be a namespaced Bedrock identifier")
    if config["timeout_seconds"] <= config["settle_seconds"] or config["settle_seconds"] < 0:
        raise SetupError("timeout_seconds must exceed nonnegative settle_seconds")
    return config


def discover():
    """Discover both GDK and legacy locations without choosing an account/world."""
    result = {"log_directories": [], "worlds": []}
    roaming = Path(os.environ.get("APPDATA", "")) / "Minecraft Bedrock"
    legacy = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState"
    for path in (roaming / "logs", legacy / "logs"):
        if path.is_dir():
            result["log_directories"].append(str(path.resolve()))
    roots = []
    for root, logs in com_mojang_roots(discovery=True):
        roots.append(root)
        if logs is not None:
            result["log_directories"].append(str(logs))
    for data_root in roots:
        for world in sorted((data_root / "minecraftWorlds").glob("*")):
            if (world / "level.dat").is_file():
                name = world / "levelname.txt"
                result["worlds"].append({
                    "path": str(world.resolve()),
                    "name": name.read_text(encoding="utf-8-sig").strip() if name.exists() else world.name,
                })
    return result


def run_game(root, config, run_id, output, client=None):
    """Client Smoke Run: deploy to the Dedicated Test World, then let the platform client (bedrock_client)
    launch it, deliver its verdict, take screenshots, and close; shape the stages of the report."""
    client = client_for_platform() if client is None else client
    local = bootstrap(root, config, client)
    world = Path(local["world"]).absolute()
    logs_path = Path(local["log_directory"])
    if not logs_path.is_dir():
        raise SetupError("Configured content log directory is missing")
    deploy(root, config, world, run_id)
    client.launch(world, config, logs_path, output)
    screenshots = []
    attempts = []
    next_capture = time.monotonic() + 15

    def capture(output_directory):
        started = time.monotonic()
        attempt = {"directory": str(output_directory)}
        try:
            path = client.capture(output_directory)
            attempt.update(status="passed", path=path)
            return path
        except Exception as error:
            attempt.update(status="failed", error=str(error))
            print(f"Screenshot attempt {len(attempts) + 1}: {error}", flush=True)
            return None
        finally:
            attempt["elapsed_seconds"] = round(time.monotonic() - started, 3)
            attempts.append(attempt)
            write_json(output / "capture-attempts.json", attempts)

    def capture_progress():
        nonlocal next_capture
        if not config.get("showcase") or time.monotonic() < next_capture:
            return
        frame = output / "screenshots" / f"{len(attempts) + 1:03}"
        frame.mkdir(parents=True, exist_ok=True)
        path = capture(frame)
        if path:
            screenshots.append(path)
        next_capture = time.monotonic() + 15

    shutdown = {"status": "not_run"}
    try:
        result = client.await_verdict(config, run_id, output, on_poll=capture_progress)
        result["screenshots"] = screenshots
        path = capture(output)
        if path:
            result["screenshot"] = path
        else:
            result["screenshot_note"] = attempts[-1]["error"]
    finally:
        try:
            client.close(output)
            shutdown["status"] = "passed"
        except Exception as error:
            shutdown.update(status="failed", error=str(error))
        write_json(output / "shutdown.json", shutdown)
    result = client.finish(result, config, run_id, output)
    required = bool(config.get("showcase"))
    capture_passed = len(screenshots) >= 2 if required else bool(result.get("screenshot"))
    platform_stages = client.stages(result)
    result["stages"] = {
        "gameplay": platform_stages.pop("gameplay"),
        "content_logs": {"status": result["status"], "errors": list(result["errors"]),
                         "warnings": list(result["warnings"])},
        "screenshots": {"status": "passed" if capture_passed else "failed",
                        "required": required, "attempts": attempts},
        "shutdown": shutdown,
        **platform_stages,
    }
    result["coverage"] = {name: "not_verified" for name in
                          ("visual_appearance", "audio_playback", "player_input", "multiplayer", "other_devices")}
    if required and not capture_passed:
        result["errors"].append("Showcase requires at least two successful screenshots")
        result["status"] = "failed"
    if shutdown["status"] == "failed":
        result["errors"].append(shutdown["error"])
        result["status"] = "failed"
    return result


def run_scenario_stage(root, config, run_id, output, only=None):
    if __package__:
        from .bedrock_scenarios import ScenarioError, run_scenarios, select_scenarios
    else:
        from bedrock_scenarios import ScenarioError, run_scenarios, select_scenarios
    if "scenario_server" not in config:
        raise SetupError("testing/bedrock.json has no scenario_server settings")
    try:
        if only is not None:
            config = select_scenarios(config, only)
        return run_scenarios(root, config, run_id, output)
    except ScenarioError as error:
        raise SetupError(str(error)) from error


def run_client_stage(root, config, run_id, output, only=None):
    if __package__:
        from .client_checks import run_client_input
    else:
        from client_checks import run_client_input
    return run_client_input(root, config, run_id, output, only)


def evidence(root, config):
    """What an acceptance record needs to identify the build a run tested (docs/ACCEPTANCE_COVERAGE.md)."""
    def git(*args):
        try:
            completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout if completed.returncode == 0 else None

    revision = git("rev-parse", "HEAD")
    # --no-renames lists a rename as its deleted and added paths, so every entry is one plain path.
    status = git("status", "--porcelain", "--no-renames") if revision is not None else None
    changed = sorted(line[3:] for line in status.splitlines()) if status is not None else None
    try:
        version = ".".join(map(str, read_json(root / config["behavior_pack"] / "manifest.json")["header"]["version"]))
    except (OSError, ValueError, KeyError, TypeError):
        version = None  # the record says it is unknown; it must not fail the run it describes
    return {
        "revision": revision.strip() if revision is not None else None,
        "working_tree_clean": not changed if changed is not None else None,
        "changed_files": changed,
        "addon_version": version,
        "game_versions": {"linux_client": config.get("linux_client_version"),
                          "scenario_server": config.get("scenario_server", {}).get("version")},
    }


def run_static(root, config, output):
    results = []
    for index, command in enumerate(config["static_commands"], 1):
        argv = [part.replace("{python}", sys.executable).replace("{report_dir}", str(output)) for part in command]
        print("Running: " + subprocess.list2cmdline(argv), flush=True)
        try:
            completed = subprocess.run(argv, cwd=root, capture_output=True, text=True, errors="replace",
                                       timeout=config["static_timeout_seconds"])
            log = completed.stdout + completed.stderr
            code = completed.returncode
        except subprocess.TimeoutExpired as error:
            log = "Static command timed out\n" + str(error)
            code = 1
        (output / f"static-{index}.log").write_text(log, encoding="utf-8")
        print(log, end="" if log.endswith("\n") else "\n", flush=True)
        results.append({"command": argv, "exit_code": code})
        if code:
            break
    return {"status": "passed" if results and all(item["exit_code"] == 0 for item in results) else "failed",
            "commands": results}


def main(argv=None, root=ROOT, client=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["doctor", "bootstrap", "configure", "static", "scenarios", "game", "client", "all"])
    parser.add_argument("--world", help="Existing fresh dedicated world directory; configure only")
    parser.add_argument("--log-directory", help="Content log directory; configure only")
    parser.add_argument("--only", help="Comma-separated scenario names (scenarios mode) or client check names (client mode)")
    args = parser.parse_args(argv)
    root = Path(root).resolve()
    run_id = uuid.uuid4().hex
    output = root / "dist/bedrock-tests" / run_id
    output.mkdir(parents=True, exist_ok=True)
    report = {"run_id": run_id, "mode": args.mode, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "status": "blocked", "exit_code": 2}
    try:
        config = load_config(root)
        report["evidence"] = evidence(root, config)
        if args.mode in ("bootstrap", "configure") and client is None:
            client = client_for_platform()
        if args.mode == "doctor":
            report["discovery"] = discover()
            report["configured"] = (root / "testing/bedrock.local.json").exists()
            print(json.dumps({"discovery": report["discovery"], "configured": report["configured"]}, indent=2))
            report.update(status="diagnostic", exit_code=0)
        elif args.mode == "bootstrap":
            report["world_setup"] = bootstrap(root, config, client)
            report.update(status="configured", exit_code=0)
        elif args.mode == "configure":
            if not args.world or not args.log_directory:
                raise SetupError("configure requires --world and --log-directory; use doctor to find paths")
            configure(root, config, args.world, args.log_directory, client)
            report.update(status="configured", exit_code=0)
        else:
            if args.world or args.log_directory:
                raise SetupError("World/log overrides are only accepted by configure")
            if args.only is not None and args.mode not in ("scenarios", "client"):
                raise SetupError("--only is only accepted by scenarios and client")
            report["only"] = args.only
            if args.mode in ("static", "all"):
                report["static"] = run_static(root, config, output)
                if report["static"]["status"] != "passed":
                    report.update(status="failed", exit_code=1)
                    return report["exit_code"]
            if args.mode == "scenarios" or (args.mode == "all" and "scenario_server" in config and not WINDOWS):
                report["scenarios"] = run_scenario_stage(root, config, run_id, output, args.only)
                if report["scenarios"]["status"] != "passed":
                    report.update(status="failed", exit_code=1)
                    return report["exit_code"]
            if args.mode == "client":
                # Client Input Run (ADR-0019): local only, and never part of All, since it takes over the desktop.
                if WINDOWS:
                    raise SetupError("The Client Input Run drives the Linux client only")
                report["client_input"] = run_client_stage(root, config, run_id, output, args.only)
                if report["client_input"]["status"] != "passed":
                    report.update(status="failed", exit_code=1)
                    return report["exit_code"]
            if args.mode in ("game", "all"):
                report["game"] = run_game(root, config, run_id, output, client)
                if report["game"]["status"] != "passed":
                    report.update(status="failed", exit_code=1)
                    return report["exit_code"]
            report.update(status="passed", exit_code=0)
    except KeyboardInterrupt:
        report.update(status="interrupted", exit_code=130, error="Interrupted by user")
    except SetupError as error:
        report.update(status="blocked", exit_code=2, error=str(error))
    except Exception as error:
        report.update(status="failed", exit_code=1, error=f"{type(error).__name__}: {error}")
    finally:
        report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(output / "report.json", report)
        write_json(root / "dist/bedrock-tests/latest.json", report)
        print(f"{report['status'].upper()}: {output / 'report.json'}", flush=True)
        if "error" in report:
            print(report["error"], flush=True)
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
