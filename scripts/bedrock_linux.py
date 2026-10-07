"""Linux client control for the Bedrock smoke runner: flatpak mcpelauncher on KDE Wayland."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from urllib.parse import quote
import uuid

try:
    from .linux_input import FocusLost
except ImportError:
    from linux_input import FocusLost


APP_ID = "io.mrarm.mcpelauncher"
KWIN_SCRIPT = "addon-test-minecraft"
# Raise the game window (caption "Minecraft"; the launcher UI is "Linux Minecraft Launcher").
ACTIVATE_JS = """for (const w of workspace.windowList()) {
  if (w.caption === "Minecraft" && w.normalWindow) { w.minimized = false; workspace.activeWindow = w; }
}
"""
CLOSE_JS = """for (const w of workspace.windowList()) {
  if (w.caption === "Minecraft" && w.normalWindow) { w.closeWindow(); }
}
"""
# KWin scripts cannot return values; this one prints the active window, tagged with a nonce, to the journal.
FOCUS_JS = """const w = workspace.activeWindow;
print("%s " + JSON.stringify(w ? {caption: w.caption, pid: w.pid} : null));
"""


class ClientError(Exception):
    pass


def data_dir():
    return Path.home() / ".var/app" / APP_ID / "data/mcpelauncher"


def client_running():
    try:
        listing = subprocess.run(["flatpak", "ps", "--columns=application"], capture_output=True,
                                 text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ClientError(f"Could not list flatpak instances: {error}") from error
    if listing.returncode:
        raise ClientError("flatpak ps failed: " + listing.stderr.strip())
    return APP_ID in listing.stdout.split()


def updates_mod(data):
    """The newest mcpelauncher-updates compatibility mod, as the launcher UI selects it."""
    mods = [path for path in (data / "mods/mcpelauncher-updates").glob("*/x86_64")
            if path.is_dir() and re.fullmatch(r"\d+(?:\.\d+)*", path.parent.name)]
    return max(mods, key=lambda path: tuple(int(part) for part in path.parent.name.split(".")), default=None)


def launch(world_name, version, log_path):
    data = data_dir()
    game = data / "versions" / version
    if not (game / "lib").is_dir():
        raise ClientError(f"Minecraft {version} is not downloaded; open the launcher and download it first")
    argv = ["flatpak", "run", "--command=mcpelauncher-client", APP_ID, "-dg", str(game),
            "-u", "minecraft://?load=" + quote(world_name, safe="")]
    mod = updates_mod(data)
    if mod:
        argv += ["-m", str(mod) + "/"]
    with open(log_path, "wb") as stream:
        # flatpak run execs into bwrap, so the new session's leader owns the whole sandbox.
        return subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)


def process_group(pgid):
    """Live (non-zombie) processes in a process group, as (pid, name)."""
    members = []
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = stat.read_text()
        except OSError:
            continue
        name = text[text.index("(") + 1:text.rindex(")")]
        state, _ppid, group = text[text.rindex(")") + 2:].split()[:3]
        if int(group) == pgid and state != "Z":
            members.append((int(stat.parent.name), name))
    return sorted(members)


def close(process, work_dir, timeout=30):
    """Close the game window normally (the world is saved), then SIGTERM only the launched game; never force-kill.

    The launched leader is the outer bwrap, but the sandbox's inner bwrap and the game share its process group
    and can outlive it, so the client counts as closed only once that whole group has exited. SIGTERM goes to the
    game itself: the inner bwrap is the sandbox's PID-namespace init and ignores it.
    """
    if process is None or _wait_for_group_exit(process, 0):
        return
    try:
        run_kwin_script(work_dir, "close-minecraft.js", CLOSE_JS)
    except (ClientError, OSError, subprocess.SubprocessError):
        pass
    if _wait_for_group_exit(process, timeout):
        return
    for pid, name in process_group(process.pid):
        if name != "bwrap":
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    if _wait_for_group_exit(process, timeout):
        return
    survivors = ", ".join(f"{pid} {name.strip()}" for pid, name in process_group(process.pid))
    raise ClientError(f"Minecraft did not close within {timeout} seconds; no process was force-stopped "
                      f"(still running: {survivors})")


def _wait_for_group_exit(process, timeout):
    deadline = time.monotonic() + timeout
    while True:
        process.poll()  # reap the leader so it does not linger as a zombie
        if not process_group(process.pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)


def activate_window(work_dir):
    run_kwin_script(work_dir, "activate-minecraft.js", ACTIVATE_JS)
    time.sleep(0.3)


def active_window(work_dir, timeout=3.0):
    """The active window's caption and pid, as KWin reports them, or None when no window is active."""
    nonce = "mt-focus-" + uuid.uuid4().hex[:12]
    run_kwin_script(work_dir, "focus-probe.js", FOCUS_JS % nonce)
    deadline = time.monotonic() + timeout
    while True:
        found = subprocess.run(["journalctl", "--user", "--since", "-60s", "-o", "cat", "--grep", nonce],
                               capture_output=True, text=True, timeout=10)
        for line in found.stdout.splitlines():
            if line.startswith(nonce + " "):
                return json.loads(line[len(nonce) + 1:])
        if time.monotonic() >= deadline:
            raise ClientError("KWin's active-window report never reached the journal")
        time.sleep(0.05)


def focus_guard(work_dir, process):
    """A guard for linux_input: input may go only to the Minecraft window of the launched sandbox."""
    def guard():
        window = active_window(work_dir)
        game_pids = {pid for pid, _ in process_group(process.pid)}
        if not window or window.get("caption") != "Minecraft" or window.get("pid") not in game_pids:
            hint = ("; the Claude app raises itself while background agents or commands run, so run Client with "
                    "nothing in the background") if window and window.get("caption") == "Claude" else ""
            raise FocusLost(f"active window is {window}, not the launched Minecraft; input stopped{hint}")
    return guard


def chat_open(screenshot):
    """True when a capture shows the Chat and Commands screen: a flat grey title bar under the launcher menu."""
    from PIL import Image, ImageStat

    with Image.open(screenshot) as image:
        width = image.width
        r, g, b = ImageStat.Stat(image.convert("RGB").crop((int(width * 0.2), 32, int(width * 0.8), 52))).mean
    return min(r, g, b) > 150 and max(r, g, b) - min(r, g, b) < 10


def run_kwin_script(work_dir, name, source):
    script = Path(work_dir) / name
    script.write_text(source, encoding="utf-8")
    scripting = ["qdbus6", "org.kde.KWin", "/Scripting"]
    subprocess.run(scripting + ["org.kde.kwin.Scripting.unloadScript", KWIN_SCRIPT], capture_output=True, timeout=10)
    loaded = subprocess.run(scripting + ["org.kde.kwin.Scripting.loadScript", str(script), KWIN_SCRIPT],
                            capture_output=True, text=True, timeout=10)
    if loaded.returncode or not loaded.stdout.strip().lstrip("-").isdigit() or int(loaded.stdout) < 0:
        raise ClientError("KWin refused the window activation script: " + (loaded.stderr.strip() or loaded.stdout.strip()))
    try:
        subprocess.run(["qdbus6", "org.kde.KWin", f"/Scripting/Script{loaded.stdout.strip()}", "org.kde.kwin.Script.run"],
                       capture_output=True, timeout=10, check=True)
    finally:
        subprocess.run(scripting + ["org.kde.kwin.Scripting.unloadScript", KWIN_SCRIPT], capture_output=True, timeout=10)


def capture(output):
    from PIL import Image

    output = Path(output)
    target = output / "minecraft.png"
    try:
        activate_window(output)
        subprocess.run(["spectacle", "--background", "--nonotify", "--activewindow",
                        "--no-decoration", "--no-shadow", "--output", str(target)],
                       capture_output=True, text=True, timeout=20, check=True)
    except FileNotFoundError as error:
        raise ClientError(f"{error.filename} is required for Linux screenshots") from error
    except subprocess.TimeoutExpired as error:
        raise ClientError("Screenshot capture exceeded 20 seconds") from error
    except subprocess.CalledProcessError as error:
        raise ClientError(f"{error.cmd[0]} failed: {(error.stderr or '').strip()}") from error
    if not target.is_file():
        raise ClientError("spectacle produced no screenshot file")
    with Image.open(target) as image:
        if not any(lo != hi for lo, hi in image.convert("RGB").getextrema()):
            raise ClientError("Minecraft returned an empty or uniform capture")
    return str(target)
