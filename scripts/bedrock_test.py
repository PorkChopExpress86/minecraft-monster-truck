"""Repository-owned Windows Bedrock smoke runner. See docs/WINDOWS_TESTING.md."""

import argparse
import ctypes
from ctypes import wintypes
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import quote
import uuid


ROOT = Path(__file__).resolve().parents[1]
MARKER = "[ADDON_TEST]"
OWNER = ".addon-test-owner.json"


class SetupError(Exception):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
    users = roaming / "Users"
    roots = list(users.glob("*/games/com.mojang/minecraftWorlds")) if users.is_dir() else []
    roots.append(legacy / "games/com.mojang/minecraftWorlds")
    for root in roots:
        for world in sorted(root.glob("*")):
            if (world / "level.dat").is_file():
                name = world / "levelname.txt"
                result["worlds"].append({
                    "path": str(world.resolve()),
                    "name": name.read_text(encoding="utf-8-sig").strip() if name.exists() else world.name,
                })
    return result


def minecraft_running():
    # Read the native process snapshot without launching a competing PowerShell process.
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise SetupError("Windows process snapshot failed")
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if entry.name.lower() in ("minecraft.windows.exe", "minecraft.exe"):
                return True
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(snapshot)


def require_closed_client():
    if os.name != "nt":
        raise SetupError("Live client testing requires Windows")
    if minecraft_running():
        raise SetupError("Close Minecraft before deployment; the runner will launch the dedicated world")


def owner_data(root, config):
    return {"repository": str(root.resolve()), "harness_uuid": config["harness_uuid"]}


def validate_world(world):
    if not world.is_dir() or not (world / "level.dat").is_file():
        raise SetupError("Select an existing dedicated test world containing level.dat")
    if world.parent.name != "minecraftWorlds":
        raise SetupError("The dedicated world must be installed in a minecraftWorlds directory")
    if world.resolve() != world.absolute():
        raise SetupError("Use the real world path, without junctions or symlinks")


def checked_destination(world, relative):
    """Resolve every replacement target before any recursive removal."""
    target = world / relative
    resolved = target.resolve()
    if resolved != target.absolute() or not resolved.is_relative_to(world.resolve()):
        raise SetupError(f"Refusing redirected deployment path: {target}")
    return target


def pack_entries(root, config):
    bp = read_json(root / config["behavior_pack"] / "manifest.json")
    rp = read_json(root / config["resource_pack"] / "manifest.json")
    return bp, rp


def deploy(root, config, world, run_id):
    validate_world(world)
    owner = checked_destination(world, OWNER)
    if not owner.exists() or read_json(owner) != owner_data(root, config):
        raise SetupError("World ownership is not configured for this repository")
    bp, rp = pack_entries(root, config)
    for name, allowed in (
        ("world_behavior_packs.json", {bp["header"]["uuid"], config["harness_uuid"]}),
        ("world_resource_packs.json", {rp["header"]["uuid"]}),
    ):
        metadata = checked_destination(world, name)
        if metadata.exists() and any(entry["pack_id"] not in allowed for entry in read_json(metadata)):
            raise SetupError("Dedicated world has unrelated active packs; deployment refused")
    suffix = config["harness_uuid"]
    destinations = [
        checked_destination(world, f"behavior_packs/addon-test-{suffix}"),
        checked_destination(world, f"resource_packs/addon-test-{suffix}"),
        checked_destination(world, f"behavior_packs/addon-harness-{suffix}"),
    ]
    for target in destinations:
        if target.exists():
            shutil.rmtree(target)
    shutil.copytree(root / config["behavior_pack"], destinations[0])
    shutil.copytree(root / config["resource_pack"], destinations[1])
    harness = destinations[2]
    shutil.copytree(root / "testing/harness", harness / "scripts")
    write_json(harness / "manifest.json", {
        "format_version": 2,
        "header": {
            "name": config["name"] + " Automated Tests (test world only)",
            "description": "Runtime smoke assertions; excluded from the distributable add-on",
            "uuid": config["harness_uuid"], "version": [1, 0, 0],
            "min_engine_version": bp["header"]["min_engine_version"],
        },
        "modules": [{"type": "script", "language": "javascript", "entry": "scripts/main.js",
                     "uuid": config["harness_module_uuid"], "version": [1, 0, 0]}],
        "dependencies": [
            {"module_name": "@minecraft/server", "version": config["script_api_version"]},
            {"uuid": bp["header"]["uuid"], "version": bp["header"]["version"]},
        ],
    })
    run = {"run_id": run_id, "entity_id": config["entity_id"],
           "required_components": config.get("required_components", []),
           "showcase": config.get("showcase", False)}
    if "expected_seat_count" in config:
        run["expected_seat_count"] = config["expected_seat_count"]
    (harness / "scripts/run_config.js").write_text(
        "export const run = " + json.dumps(run) + ";\n", encoding="utf-8",
    )
    write_json(world / "world_behavior_packs.json", [
        {"pack_id": bp["header"]["uuid"], "version": bp["header"]["version"]},
        {"pack_id": config["harness_uuid"], "version": [1, 0, 0]},
    ])
    write_json(world / "world_resource_packs.json", [
        {"pack_id": rp["header"]["uuid"], "version": rp["header"]["version"]},
    ])


def configure(root, config, world, logs):
    require_closed_client()
    world = Path(world).absolute()
    validate_world(world)
    if world.resolve() != world:
        raise SetupError("Use the real world path, without junctions or symlinks")
    logs = Path(logs).resolve()
    if not logs.is_dir():
        raise SetupError("Content log directory does not exist; enable Content Log Files in Minecraft")
    owner = checked_destination(world, OWNER)
    if owner.exists() and read_json(owner) != owner_data(root, config):
        raise SetupError("This test world belongs to another repository")
    if not owner.exists():
        # A fresh world is required: do not silently take over an existing add-on setup.
        for name in ("world_behavior_packs.json", "world_resource_packs.json"):
            metadata = checked_destination(world, name)
            if metadata.exists() and read_json(metadata):
                raise SetupError("Choose a fresh dedicated world with no active add-on packs")
        backup = root / "dist/bedrock-tests/setup" / uuid.uuid4().hex
        for name in ("world_behavior_packs.json", "world_resource_packs.json"):
            if (world / name).exists():
                backup.mkdir(parents=True, exist_ok=True)
                shutil.copy2(world / name, backup / name)
        for relative in (f"behavior_packs/addon-test-{config['harness_uuid']}",
                         f"resource_packs/addon-test-{config['harness_uuid']}",
                         f"behavior_packs/addon-harness-{config['harness_uuid']}"):
            if checked_destination(world, relative).exists():
                raise SetupError("A deployment destination already exists in an unowned world")
        write_json(owner, owner_data(root, config))
    deploy(root, config, world, "setup-" + uuid.uuid4().hex)
    write_json(root / "testing/bedrock.local.json", {"world": str(world), "log_directory": str(logs)})
    print("Configured dedicated world. Close Minecraft before each run; the runner opens it automatically.")


def log_files(directory):
    return sorted(set(directory.glob("*.log")) | set(directory.glob("*.txt")))


def bootstrap(root, config):
    require_closed_client()
    if __package__:
        from .bedrock_world import create_world, enable_logging
    else:
        from bedrock_world import create_world, enable_logging
    local_path = root / "testing/bedrock.local.json"
    try:
        if local_path.exists():
            local = read_json(local_path)
            world = Path(local["world"])
            validate_world(world)
            if read_json(checked_destination(world, OWNER)) != owner_data(root, config):
                raise SetupError("Configured world belongs to another repository")
            local["log_directory"] = str(enable_logging(root, world.parent.parent))
            write_json(local_path, local)
        else:
            local = create_world(root, config)
            configure(root, config, local["world"], local["log_directory"])
    except ValueError as error:
        raise SetupError(str(error)) from error
    print("Automatic world setup ready: " + local["world"], flush=True)
    return local


class FreshLogs:
    """Read only new bytes, handling newly created, truncated, and rotated logs."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.state = {}
        self.pending = {}
        for path in log_files(self.directory):
            stat = path.stat()
            self.state[path] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)

    def read(self):
        lines = []
        for path in log_files(self.directory):
            stat = path.stat()
            old_inode, offset, old_mtime = self.state.get(path, (stat.st_ino, 0, 0))
            if stat.st_ino != old_inode or stat.st_size < offset or (stat.st_size == offset and stat.st_mtime_ns != old_mtime):
                offset = 0
                self.pending.pop(path, None)
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read()
                end = stream.tell()
            self.state[path] = (stat.st_ino, end, stat.st_mtime_ns)
            data = self.pending.get(path, b"") + data
            parts = data.split(b"\n")
            self.pending[path] = parts.pop()
            lines.extend((str(path), part.decode("utf-8", errors="replace").rstrip("\r")) for part in parts)
        return lines


def evaluate_lines(lines, run_id, entity_id):
    errors, warnings, markers = [], [], []
    for _, line in lines:
        if MARKER in line:
            marker = None
            try:
                marker, _ = json.JSONDecoder().raw_decode(line.split(MARKER, 1)[1].lstrip())
            except (ValueError, TypeError):
                pass
            if isinstance(marker, dict) and marker.get("run_id") == run_id and marker.get("entity_id") == entity_id:
                if marker.get("status") == "FAIL":
                    errors.append("Harness failed: " + str(marker.get("error", "unspecified failure")))
                    continue
                elif marker.get("status") == "PASS" and isinstance(marker.get("checks"), list) and marker["checks"]:
                    if not re.search(r"\b(?:error|fatal)\b", line.split(MARKER, 1)[0], re.I):
                        markers.append(marker)
                        continue
            errors.append("Invalid or unexpected harness diagnostic: " + line)
            continue
        if re.search(r"\b(?:error|fatal)\b", line, re.I):
            errors.append(line)
        elif re.search(r"\bwarn(?:ing)?\b", line, re.I):
            warnings.append(line)
    return errors, warnings, markers


def await_result(logs, config, run_id, output, clock=time.monotonic, sleep=time.sleep, on_poll=None):
    started = clock()
    deadline = started + config["timeout_seconds"]
    passed_at = None
    marker = None
    errors, warnings = [], []
    with (output / "content.log").open("w", encoding="utf-8") as evidence:
        while clock() < deadline:
            if on_poll:
                on_poll()
            lines = logs.read()
            for path, line in lines:
                evidence.write(f"{path}: {line}\n")
            evidence.flush()
            new_errors, new_warnings, markers = evaluate_lines(lines, run_id, config["entity_id"])
            errors.extend(new_errors)
            warnings.extend(new_warnings)
            if markers and passed_at is None:
                marker = markers[0]
                passed_at = clock()
            if errors or warnings:
                return {"status": "failed", "errors": errors, "warnings": warnings, "marker": marker}
            if (passed_at is not None and clock() - passed_at >= config["settle_seconds"]
                    and clock() - started >= config.get("observe_seconds", 0)
                    and not any(part.strip() for part in logs.pending.values())):
                return {"status": "passed", "errors": [], "warnings": [], "marker": marker}
            sleep(0.25)
    return {"status": "failed", "errors": ["Timed out waiting for a fresh harness PASS and clean log settling period"],
            "warnings": warnings, "marker": marker, "stream_wait_expired": True}


def finalize_game_logs(logs, result, config, run_id, output):
    """The Windows client can buffer all content-log output until normal shutdown."""
    lines = logs.read()
    for path, data in logs.pending.items():
        if data.strip():
            lines.append((str(path), data.decode("utf-8", errors="replace")))
    logs.pending.clear()
    with (output / "content.log").open("a", encoding="utf-8") as evidence:
        for path, line in lines:
            evidence.write(f"{path}: {line}\n")
    errors, warnings, markers = evaluate_lines(lines, run_id, config["entity_id"])
    # Expiry of the streaming wait is provisional: shutdown may flush a real result.
    if not result.pop("stream_wait_expired", False):
        errors = result["errors"] + errors
    warnings = result["warnings"] + warnings
    marker = result["marker"] or (markers[0] if markers else None)
    if not marker:
        errors.append("No fresh harness PASS was recorded before the client closed")
    result.update(status="failed" if errors or warnings else "passed", errors=errors,
                  warnings=warnings, marker=marker, final_logs_collected=True)
    return result


def find_game_window():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    def visit(hwnd, _):
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, len(title))
        if user32.IsWindowVisible(hwnd) and title.value in ("Minecraft", "Minecraft for Windows"):
            windows.append(hwnd)
        return True

    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(callback_type(visit), 0)
    return windows[0] if windows else None


def capture_game(output):
    command = (
        "import sys; from pathlib import Path; from bedrock_test import _capture_game; "
        "print(_capture_game(Path(sys.argv[1])))"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", command, str(Path(output).resolve())],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
            timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        diagnostic = error.stderr or b""
        if isinstance(diagnostic, bytes):
            diagnostic = diagnostic.decode("utf-8", errors="replace")
        (Path(output) / "capture-trace.log").write_text(diagnostic, encoding="utf-8")
        raise SetupError(f"Minecraft screenshot capture exceeded 20 seconds; {diagnostic.strip() or 'helper did not start'}") from error
    (Path(output) / "capture-trace.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode:
        raise SetupError(completed.stderr.strip().splitlines()[-1] if completed.stderr else "Screenshot helper failed")
    path = Path(completed.stdout.strip())
    if not path.is_file() or path.parent.resolve() != Path(output).resolve():
        raise SetupError("Screenshot helper returned no capture file in the requested directory")
    return str(path)


def _capture_game(output):
    def stage(name):
        print(f"capture stage: {name}", file=sys.stderr, flush=True)

    stage("import_imagegrab")
    from PIL import ImageGrab
    # Keep Win32 coordinates and captured pixels in the same space on scaled displays.
    ctypes.WinDLL("user32").SetProcessDPIAware()
    stage("find_window")
    hwnd = find_game_window()
    if not hwnd:
        raise SetupError("Minecraft window unavailable; screenshot omitted")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.IsIconic.argtypes = [wintypes.HWND]
    if user32.IsIconic(hwnd):
        raise SetupError("Minecraft is minimized; restore it before capturing")
    stage("client_rectangle")
    rect = wintypes.RECT()
    if (not user32.GetClientRect(hwnd, ctypes.byref(rect))
            or rect.right <= rect.left or rect.bottom <= rect.top):
        raise SetupError("Minecraft window has no capture area")
    target = output / "minecraft.png"
    stage("grab_pixels")
    # HWND capture avoids foreground manipulation and never samples another app.
    captured = ImageGrab.grab(window=hwnd)
    stage("validate_pixels")
    if not any(lo != hi for lo, hi in captured.convert("RGB").getextrema()):
        # Some hardware-accelerated renderers return a uniform HWND surface.
        stage("foreground_fallback")
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        if user32.GetForegroundWindow() != hwnd:
            user32.ShowWindowAsync(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.2)
        if user32.GetForegroundWindow() != hwnd:
            raise SetupError("Empty or uniform window capture; Minecraft is not foreground for fallback")
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        origin = wintypes.POINT()
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)) or not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            raise SetupError("Minecraft client rectangle unavailable for fallback")
        stage("grab_foreground_pixels")
        captured = ImageGrab.grab(bbox=(origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom))
        if user32.GetForegroundWindow() != hwnd:
            raise SetupError("Minecraft lost foreground during capture; image discarded")
    if captured.width <= 0 or captured.height <= 0 or not any(lo != hi for lo, hi in captured.convert("RGB").getextrema()):
        raise SetupError("Minecraft returned an empty or uniform capture")
    stage("save_png")
    captured.save(target)
    stage("saved")
    return str(target)


def close_game():
    """Request a normal close only for the client launched by this run."""
    if not minecraft_running():
        return
    hwnd = find_game_window()
    if not hwnd:
        raise SetupError("Launched Minecraft has no closeable window; close it before the next run")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    if not user32.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE, no forced termination
        raise SetupError("Could not request Minecraft shutdown")
    deadline = time.monotonic() + 30
    while minecraft_running():
        if time.monotonic() >= deadline:
            raise SetupError("Minecraft did not close within 30 seconds; no process was force-stopped")
        time.sleep(0.5)


def run_game(root, config, run_id, output):
    local = bootstrap(root, config)
    world = Path(local["world"]).absolute()
    logs_path = Path(local["log_directory"])
    if not logs_path.is_dir():
        raise SetupError("Configured content log directory is missing")
    deploy(root, config, world, run_id)
    logs = FreshLogs(logs_path)
    os.startfile("minecraft://?load=" + quote(world.name, safe=""))
    screenshots = []
    attempts = []
    next_capture = time.monotonic() + 15

    def capture(output_directory):
        started = time.monotonic()
        attempt = {"directory": str(output_directory)}
        try:
            path = capture_game(output_directory)
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
        result = await_result(logs, config, run_id, output, on_poll=capture_progress)
        result["screenshots"] = screenshots
        path = capture(output)
        if path:
            result["screenshot"] = path
        else:
            result["screenshot_note"] = attempts[-1]["error"]
    finally:
        try:
            close_game()
            shutdown["status"] = "passed"
        except Exception as error:
            shutdown.update(status="failed", error=str(error))
        write_json(output / "shutdown.json", shutdown)
    result = finalize_game_logs(logs, result, config, run_id, output)
    required = bool(config.get("showcase"))
    capture_passed = len(screenshots) >= 2 if required else bool(result.get("screenshot"))
    result["stages"] = {
        "gameplay": {"status": "passed" if result["marker"] else "failed",
                     "checks": (result["marker"] or {}).get("checks", [])},
        "content_logs": {"status": result["status"], "errors": list(result["errors"]),
                         "warnings": list(result["warnings"])},
        "screenshots": {"status": "passed" if capture_passed else "failed",
                        "required": required, "attempts": attempts},
        "shutdown": shutdown,
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


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["doctor", "bootstrap", "configure", "static", "game", "all"])
    parser.add_argument("--world", help="Existing fresh dedicated world directory; configure only")
    parser.add_argument("--log-directory", help="Content log directory; configure only")
    args = parser.parse_args(argv)
    root = Path(root).resolve()
    run_id = uuid.uuid4().hex
    output = root / "dist/bedrock-tests" / run_id
    output.mkdir(parents=True, exist_ok=True)
    report = {"run_id": run_id, "mode": args.mode, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "status": "blocked", "exit_code": 2}
    try:
        config = load_config(root)
        if args.mode == "doctor":
            report["discovery"] = discover()
            report["configured"] = (root / "testing/bedrock.local.json").exists()
            print(json.dumps({"discovery": report["discovery"], "configured": report["configured"]}, indent=2))
            report.update(status="diagnostic", exit_code=0)
        elif args.mode == "bootstrap":
            report["world_setup"] = bootstrap(root, config)
            report.update(status="configured", exit_code=0)
        elif args.mode == "configure":
            if not args.world or not args.log_directory:
                raise SetupError("configure requires --world and --log-directory; use doctor to find paths")
            configure(root, config, args.world, args.log_directory)
            report.update(status="configured", exit_code=0)
        else:
            if args.world or args.log_directory:
                raise SetupError("World/log overrides are only accepted by configure")
            if args.mode in ("static", "all"):
                report["static"] = run_static(root, config, output)
                if report["static"]["status"] != "passed":
                    report.update(status="failed", exit_code=1)
                    return report["exit_code"]
            if args.mode in ("game", "all"):
                report["game"] = run_game(root, config, run_id, output)
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
