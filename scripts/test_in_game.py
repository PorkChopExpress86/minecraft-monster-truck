import ctypes
from dataclasses import dataclass, field
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import List, Optional

DEFAULT_MOJANG_PATH = Path(
    os.path.expandvars(
        r"%LOCALAPPDATA%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"
    )
)

DEFAULT_CONTENT_LOG_PATH = Path(
    os.path.expandvars(
        r"%LOCALAPPDATA%\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\logs\content_log.txt"
    )
)

# Win32 Constants and Structs for Simulated Input
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _anonymous_ = ("_union",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_union", _INPUT_UNION),
    ]

@dataclass
class ContentLogResult:
    has_errors: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    end_offset: int = 0

@dataclass
class TestReport:
    __test__ = False
    passed: bool
    errors_count: int = 0
    warnings_count: int = 0
    error_details: List[str] = field(default_factory=list)
    warning_details: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    content_log_result: Optional[ContentLogResult] = None
    summary: str = ""

def scan_content_log(log_path=None, start_offset: int = 0) -> ContentLogResult:
    """
    Scans the Bedrock content_log.txt file starting from start_offset for
    [ERROR] and [WARNING] entries.
    """
    path = Path(log_path) if log_path else DEFAULT_CONTENT_LOG_PATH
    if not path.exists():
        return ContentLogResult(has_errors=False, end_offset=0)

    errors: List[str] = []
    warnings: List[str] = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        f.seek(start_offset)
        new_lines = f.readlines()
        end_offset = f.tell()

    for line in new_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if " ERROR]" in line_clean or "[ERROR]" in line_clean or " ERROR " in line_clean:
            errors.append(line_clean)
        elif " WARNING]" in line_clean or "[WARNING]" in line_clean or " WARNING " in line_clean:
            warnings.append(line_clean)

    return ContentLogResult(
        has_errors=len(errors) > 0,
        errors=errors,
        warnings=warnings,
        end_offset=end_offset,
    )

def sync_addon_to_development_packs(repo_root=None, mojang_dir=None):
    """
    Syncs the Monster Truck behavior and resource packs directly to
    development_behavior_packs and development_resource_packs.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    mojang = Path(mojang_dir) if mojang_dir else DEFAULT_MOJANG_PATH

    bp_src = root / "behavior_packs" / "MonsterTruck_BP"
    rp_src = root / "resource_packs" / "MonsterTruck_RP"

    if not bp_src.exists():
        raise FileNotFoundError(f"Behavior pack source not found: {bp_src}")
    if not rp_src.exists():
        raise FileNotFoundError(f"Resource pack source not found: {rp_src}")

    bp_dest = mojang / "development_behavior_packs" / "MonsterTruck_BP"
    rp_dest = mojang / "development_resource_packs" / "MonsterTruck_RP"

    bp_dest.parent.mkdir(parents=True, exist_ok=True)
    rp_dest.parent.mkdir(parents=True, exist_ok=True)

    if bp_dest.exists():
        shutil.rmtree(bp_dest)
    if rp_dest.exists():
        shutil.rmtree(rp_dest)

    shutil.copytree(bp_src, bp_dest)
    shutil.copytree(rp_src, rp_dest)

    return bp_dest, rp_dest

KEYEVENTF_SCANCODE = 0x0008

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

def _send_key_event(vk_code: int = 0, scan_code: int = 0, flags: int = 0):
    """Sends down/up key event pair via SendInput."""
    inp_down = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(wVk=vk_code, wScan=scan_code, dwFlags=flags, time=0, dwExtraInfo=0),
    )
    inp_up = INPUT(
        type=INPUT_KEYBOARD,
        ki=KEYBDINPUT(wVk=vk_code, wScan=scan_code, dwFlags=flags | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0),
    )
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
    time.sleep(0.02)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
    time.sleep(0.02)

def send_unicode_char(char: str):
    """Sends a single character keypress using Win32 SendInput KEYEVENTF_UNICODE."""
    _send_key_event(scan_code=ord(char), flags=KEYEVENTF_UNICODE)

def send_virtual_key(vk_code: int):
    """Sends a virtual key code press and release mapped to DirectInput hardware scancode."""
    scan_code = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    _send_key_event(vk_code=vk_code, scan_code=scan_code, flags=KEYEVENTF_SCANCODE)

def type_text(text: str):
    """Simulates typing a string via unicode input."""
    for ch in text:
        send_unicode_char(ch)

def find_minecraft_window() -> Optional[int]:
    """Finds the HWND handle of the Minecraft client window."""
    user32 = ctypes.windll.user32
    matches: List[int] = []

    def enum_windows_callback(hwnd: int, extra: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                if "Minecraft" in title:
                    matches.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
    return matches[0] if matches else None

def focus_minecraft_window() -> bool:
    """Brings Minecraft to the foreground."""
    hwnd = find_minecraft_window()
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True

def capture_screenshot(output_path: Path, hwnd: Optional[int] = None) -> Path:
    """Captures a screenshot of the Minecraft window (or full display if hwnd not given)."""
    from PIL import ImageGrab
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bbox = None
    if hwnd:
        rect = RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            if rect.right > rect.left and rect.bottom > rect.top:
                bbox = (rect.left, rect.top, rect.right, rect.bottom)
    img = ImageGrab.grab(bbox=bbox)
    img.save(output_path)
    return output_path

def execute_summon_sequence(command: str = "/summon blake:monster_truck ~ ~ ~") -> None:
    """
    Opens chat, types the summon command, and presses Enter.
    """
    # Send '/' directly to open chat and start command entry
    send_unicode_char("/")
    time.sleep(0.3)
    # Strip leading '/' if typing command since '/' already opens chat in command mode
    payload = command[1:] if command.startswith("/") else command
    type_text(payload)
    time.sleep(0.2)
    send_virtual_key(VK_RETURN)

def run_in_game_test(
    repo_root=None,
    mojang_dir=None,
    content_log_path=None,
    output_dir=None,
    dry_run: bool = False,
    summon_command: str = "/summon blake:monster_truck ~ ~ ~",
    initial_log_offset: Optional[int] = None,
) -> TestReport:
    """
    Executes the automated in-game test cycle:
    1. Records starting offset of content_log.txt
    2. Syncs pack files into development_*_packs
    3. Launches/focuses Minecraft and executes summon sequence (if not dry_run)
    4. Captures screenshot
    5. Checks content_log.txt for errors and missing texture warnings
    6. Returns structured TestReport
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parent.parent
    dist_out = Path(output_dir) if output_dir else (root / "dist" / "in_game_tests")
    dist_out.mkdir(parents=True, exist_ok=True)

    log_path = Path(content_log_path) if content_log_path else DEFAULT_CONTENT_LOG_PATH
    start_offset = 0
    if initial_log_offset is not None:
        start_offset = initial_log_offset
    elif log_path.exists():
        start_offset = log_path.stat().st_size

    # 1. Sync pack files
    sync_addon_to_development_packs(repo_root=root, mojang_dir=mojang_dir)

    screenshot_file: Optional[str] = None

    if not dry_run:
        # Launch Minecraft if not already running
        hwnd = find_minecraft_window()
        if not hwnd:
            print("[INFO] Launching Minecraft Bedrock...")
            subprocess.Popen(["cmd.exe", "/c", "start", "minecraft:"])
            time.sleep(8.0)
            hwnd = find_minecraft_window()

        focus_minecraft_window()
        time.sleep(1.0)

        # Execute summon command
        print(f"[INFO] Executing in-game command: {summon_command}")
        execute_summon_sequence(summon_command)

        # Wait 2 seconds for entity model and texture rendering
        time.sleep(2.0)

        # Snap screenshot
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_target = dist_out / f"monster_truck_{timestamp}.png"
        capture_screenshot(screenshot_target, hwnd=hwnd)
        screenshot_file = str(screenshot_target)
        print(f"[INFO] Saved screenshot: {screenshot_file}")

    # 2. Content Log Verification
    log_result = scan_content_log(log_path, start_offset=start_offset)

    has_texture_or_schema_warnings = any(
        "texture" in w.lower() or "schema" in w.lower() for w in log_result.warnings
    )
    passed = (not log_result.has_errors) and (not has_texture_or_schema_warnings)
    summary = (
        "In-game test passed with 0 errors/warnings."
        if passed
        else f"In-game test failed with {len(log_result.errors)} error(s) and {len(log_result.warnings)} warning(s) in content_log.txt."
    )

    return TestReport(
        passed=passed,
        errors_count=len(log_result.errors),
        warnings_count=len(log_result.warnings),
        error_details=log_result.errors,
        warning_details=log_result.warnings,
        screenshot_path=screenshot_file,
        content_log_result=log_result,
        summary=summary,
    )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Automated In-Game Monster Truck Test Runner")
    parser.add_argument("--dry-run", action="store_true", help="Sync files and verify logs without triggering game inputs")
    parser.add_argument("--command", default="/summon blake:monster_truck ~ ~ ~", help="Command to execute in game")
    args = parser.parse_args()

    report = run_in_game_test(dry_run=args.dry_run, summon_command=args.command)
    print("\n--- Test Report ---")
    print(f"Status: {'PASSED' if report.passed else 'FAILED'}")
    print(f"Errors: {report.errors_count}")
    print(f"Warnings: {report.warnings_count}")
    if report.screenshot_path:
        print(f"Screenshot: {report.screenshot_path}")
    if report.error_details:
        print("Error details:")
        for err in report.error_details:
            print(f"  - {err}")
    exit(0 if report.passed else 1)
