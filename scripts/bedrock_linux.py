"""Linux client control for the Bedrock smoke runner: flatpak mcpelauncher on KDE Wayland."""
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from urllib.parse import quote


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


def close(process, work_dir, timeout=30):
    """Close the game window normally (the world is saved), then SIGTERM only the launched sandbox; never force-kill."""
    if process is None or process.poll() is not None:
        return
    try:
        run_kwin_script(work_dir, "close-minecraft.js", CLOSE_JS)
        process.wait(timeout)
        return
    except (ClientError, OSError, subprocess.SubprocessError):
        pass
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout)
    except subprocess.TimeoutExpired as error:
        raise ClientError(f"Minecraft did not close within {timeout} seconds; no process was force-stopped") from error


def activate_window(work_dir):
    run_kwin_script(work_dir, "activate-minecraft.js", ACTIVATE_JS)
    time.sleep(0.3)


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
