"""The game client a Client Smoke Run drives, one adapter per platform.

Every client offers the same interface to bedrock_test.run_game:
  assert_closed()                                  SetupError if Minecraft is already running
  launch(world, config, logs_directory, output)    snapshot the content logs, then open the world
  await_verdict(config, run_id, output, on_poll)   result dict once the platform's evidence is in
  capture(directory)                               path of one game-window screenshot
  close(output)                                    normal close of only the launched client
  finish(result, config, run_id, output)           fold in content-log output flushed at shutdown
  stages(result)                                   this platform's report stages

WindowsClient passes on the harness [ADDON_TEST] marker in content logs ('gameplay' stage).
LauncherClient (Linux flatpak mcpelauncher) never sees script output, so it passes on the world
loading with every deployed pack ('world_load' stage) and leaves 'gameplay' not_verified (ADR-0016).
"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote

if __package__:
    from . import bedrock_linux as linux
    from .bedrock_world import SetupError, dedicated_pack_ids
else:
    import bedrock_linux as linux
    from bedrock_world import SetupError, dedicated_pack_ids


MARKER = "[ADDON_TEST]"
CLOSE_FIRST = "Close Minecraft before deployment; the runner will launch the dedicated world"


def log_files(directory):
    return sorted(set(directory.glob("*.log")) | set(directory.glob("*.txt")))


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


def await_result(logs, config, run_id, output, clock=time.monotonic, sleep=time.sleep,
                 on_poll=None):
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


def await_client_load(client, stdout_path, world, pack_ids, config, clock=time.monotonic, sleep=time.sleep,
                      on_poll=None):
    """Linux client: script console output never reaches a readable log, so the verdict is
    that the dedicated world opened with every deployed pack and the player spawned (ADR-0016)."""
    started = clock()
    expected = {"world opened": f"Opening level '{world / 'db'}'", "player spawned": "Player Spawned:"}
    expected.update({f"pack {pack_id} loaded": pack_id for pack_id in pack_ids})
    seen, offset, loaded_at = set(), 0, None
    while clock() < started + config["timeout_seconds"] or loaded_at is not None:
        if on_poll:
            on_poll()
        with open(stdout_path, "rb") as stream:
            stream.seek(offset)
            data = stream.read()
        complete = data[:data.rfind(b"\n") + 1]
        offset += len(complete)
        for line in complete.decode("utf-8", errors="replace").splitlines():
            if "Pack Stack" not in line and "Opening level" not in line and "Player Spawned" not in line:
                continue
            seen.update(name for name, needle in expected.items() if needle in line)
        if loaded_at is None and seen == set(expected):
            loaded_at = clock()
        if client.poll() is not None:
            return {"status": "failed", "errors": ["Minecraft exited during the run (code %s)" % client.returncode],
                    "warnings": [], "marker": None, "load_checks": sorted(seen)}
        if loaded_at is not None and clock() - started >= config.get("observe_seconds", 0):
            return {"status": "passed", "errors": [], "warnings": [], "marker": None, "load_checks": sorted(seen)}
        sleep(0.25)
    missing = sorted(set(expected) - seen)
    return {"status": "failed", "errors": ["Timed out before the dedicated world loaded: missing " + ", ".join(missing)],
            "warnings": [], "marker": None, "load_checks": sorted(seen)}


def finalize_game_logs(logs, result, config, run_id, output, require_marker=True):
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
    if not marker and require_marker:
        errors.append("No fresh harness PASS was recorded before the client closed")
    result.update(status="failed" if errors or warnings else "passed", errors=errors,
                  warnings=warnings, marker=marker, final_logs_collected=True)
    return result


class ContentLogClient:
    """Shared by both adapters: content logs are snapshotted before launch and re-read after close."""

    requires_marker = True
    logs = None

    def watch_logs(self, logs_directory):
        self.logs = FreshLogs(logs_directory)

    def finish(self, result, config, run_id, output):
        return finalize_game_logs(self.logs, result, config, run_id, output, require_marker=self.requires_marker)


# Windows: Minecraft for Windows (GDK or legacy UWP).

class Win32User32:
    """The user32 port: the real DLL, plus enum_windows so the EnumWindows callback type stays inside the port."""

    def __init__(self):
        self._dll = ctypes.WinDLL("user32", use_last_error=True)

    def __getattr__(self, name):
        return getattr(self._dll, name)

    def enum_windows(self, visit):
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._dll.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        self._dll.EnumWindows(callback_type(visit), 0)


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


def find_game_window(user32):
    windows = []
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    def visit(hwnd, _):
        title = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title, len(title))
        if user32.IsWindowVisible(hwnd) and title.value in ("Minecraft", "Minecraft for Windows"):
            windows.append(hwnd)
        return True

    user32.enum_windows(visit)
    return windows[0] if windows else None


def _capture_game(output, user32=None):
    def stage(name):
        print(f"capture stage: {name}", file=sys.stderr, flush=True)

    stage("import_imagegrab")
    from PIL import ImageGrab
    user32 = Win32User32() if user32 is None else user32
    # Keep Win32 coordinates and captured pixels in the same space on scaled displays.
    user32.SetProcessDPIAware()
    stage("find_window")
    hwnd = find_game_window(user32)
    if not hwnd:
        raise SetupError("Minecraft window unavailable; screenshot omitted")
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


class WindowsClient(ContentLogClient):
    """Minecraft for Windows. user32 and running are the Win32 ports (defaults: the real DLL and process snapshot)."""

    def __init__(self, user32=None, running=None):
        self._user32 = user32
        self.running = running or minecraft_running

    @property
    def user32(self):
        if self._user32 is None:
            self._user32 = Win32User32()
        return self._user32

    def assert_closed(self):
        if self.running():
            raise SetupError(CLOSE_FIRST)

    def open_uri(self, uri):
        os.startfile(uri)

    def launch(self, world, config, logs_directory, output):
        self.watch_logs(logs_directory)
        self.open_uri("minecraft://?load=" + quote(world.name, safe=""))

    def await_verdict(self, config, run_id, output, on_poll=None):
        return await_result(self.logs, config, run_id, output, on_poll=on_poll)

    def capture(self, directory):
        """Capture in a helper process with a hard timeout, so a hung Win32/Pillow call cannot stall the run."""
        command = (
            "import sys; from pathlib import Path; from bedrock_client import _capture_game; "
            "print(_capture_game(Path(sys.argv[1])))"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", command, str(Path(directory).resolve())],
                cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
                timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            diagnostic = error.stderr or b""
            if isinstance(diagnostic, bytes):
                diagnostic = diagnostic.decode("utf-8", errors="replace")
            (Path(directory) / "capture-trace.log").write_text(diagnostic, encoding="utf-8")
            raise SetupError(f"Minecraft screenshot capture exceeded 20 seconds; {diagnostic.strip() or 'helper did not start'}") from error
        (Path(directory) / "capture-trace.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise SetupError(completed.stderr.strip().splitlines()[-1] if completed.stderr else "Screenshot helper failed")
        path = Path(completed.stdout.strip())
        if not path.is_file() or path.parent.resolve() != Path(directory).resolve():
            raise SetupError("Screenshot helper returned no capture file in the requested directory")
        return str(path)

    def close(self, output):
        """Request a normal close only for the client launched by this run."""
        if not self.running():
            return
        hwnd = find_game_window(self.user32)
        if not hwnd:
            raise SetupError("Launched Minecraft has no closeable window; close it before the next run")
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        if not self.user32.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE, no forced termination
            raise SetupError("Could not request Minecraft shutdown")
        deadline = time.monotonic() + 30
        while self.running():
            if time.monotonic() >= deadline:
                raise SetupError("Minecraft did not close within 30 seconds; no process was force-stopped")
            time.sleep(0.5)

    def stages(self, result):
        return {"gameplay": {"status": "passed" if result["marker"] else "failed",
                             "checks": (result["marker"] or {}).get("checks", [])}}


# Linux: flatpak Minecraft Bedrock Launcher (bedrock_linux).

class LauncherClient(ContentLogClient):
    """Linux mcpelauncher. launcher is the bedrock_linux module (process, KWin window and spectacle control)."""

    requires_marker = False

    def __init__(self, launcher=linux):
        self.launcher = launcher
        self.process = None
        self.world = None

    def assert_closed(self):
        try:
            running = self.launcher.client_running()
        except self.launcher.ClientError as error:
            raise SetupError(str(error)) from error
        if running:
            raise SetupError(CLOSE_FIRST)

    def launch(self, world, config, logs_directory, output):
        self.watch_logs(logs_directory)
        self.world = world
        try:
            self.process = self.launcher.launch(world.name, config["linux_client_version"], output / "client-stdout.log")
        except self.launcher.ClientError as error:
            raise SetupError(str(error)) from error

    def await_verdict(self, config, run_id, output, on_poll=None):
        # The client logs only the behavior pack stack; resource packs are evidenced by screenshots.
        pack_ids = (dedicated_pack_ids(config)[0], config["harness_uuid"])
        return await_client_load(self.process, output / "client-stdout.log", self.world, pack_ids, config,
                                 on_poll=on_poll)

    def capture(self, directory):
        try:
            return self.launcher.capture(directory)
        except self.launcher.ClientError as error:
            raise SetupError(str(error)) from error

    def close(self, output):
        self.launcher.close(self.process, output)

    def stages(self, result):
        load_checks = result.pop("load_checks", [])
        return {
            "gameplay": {"status": "not_verified", "checks": [],
                         "note": "The Linux client never surfaces script output; gameplay is asserted by Scenario Runs"},
            "world_load": {
                "status": "passed" if "world opened" in load_checks and "player spawned" in load_checks
                and sum(check.startswith("pack ") for check in load_checks) == 2 else "failed",
                "checks": load_checks},
        }


def client_for_platform():
    return WindowsClient() if os.name == "nt" else LauncherClient()
