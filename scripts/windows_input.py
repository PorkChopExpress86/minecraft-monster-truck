"""Windows side of the Client Input Run: SendInput key presses into Minecraft for Windows, behind a focus guard.

linux_input.VirtualInput does the pressing, holding and focus checks on both platforms; this module supplies its
device and guard. Linux key codes (linux_input.KEYS) for the keys a run uses are the PC set-1 scan codes, so the
device sends each one as a hardware scan code, which the game reads like a physical key.
"""
import ctypes
from ctypes import wintypes
import time

try:
    from .linux_input import EV_KEY, EV_REL, FocusLost, REL_X
except ImportError:
    from linux_input import EV_KEY, EV_REL, FocusLost, REL_X

GAME_PROCESSES = ("minecraft.windows.exe", "minecraft.exe")
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0002, 0x0008
MOUSEEVENTF_MOVE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    return user32


class SendInputDevice:
    """The VirtualInput device: EV_KEY codes become scan-code key events, EV_REL relative mouse motion."""

    def __init__(self, user32=None):
        self.user32 = _user32() if user32 is None else user32

    def _send(self, event):
        if self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            raise OSError(ctypes.get_last_error(), "SendInput was blocked")

    def emit(self, etype, code, value):
        event = INPUT()
        if etype == EV_KEY:
            event.type = INPUT_KEYBOARD
            event.u.ki = KEYBDINPUT(0, code, KEYEVENTF_SCANCODE | (0 if value else KEYEVENTF_KEYUP), 0, 0)
        elif etype == EV_REL:
            event.type = INPUT_MOUSE
            dx, dy = (value, 0) if code == REL_X else (0, value)
            event.u.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, 0)
        else:
            return  # EV_SYN: SendInput delivers each event on its own
        self._send(event)

    def close(self):
        pass


def window_process(user32, hwnd):
    """(pid, lower-case image name) of the process that owns a window, or (0, None)."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return 0, None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                  ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return pid.value, None
    try:
        path = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(path))
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return pid.value, None
        return pid.value, path.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel.CloseHandle(handle)


def foreground(user32=None):
    """The foreground window as {caption, pid, process}, or None."""
    user32 = _user32() if user32 is None else user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    title = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title, len(title))
    pid, process = window_process(user32, hwnd)
    return {"caption": title.value, "pid": pid, "process": process}


def focus_guard(current=foreground):
    """A guard for VirtualInput: input may go only to a Minecraft for Windows window."""
    def guard():
        window = current()
        if not window or window["process"] not in GAME_PROCESSES:
            raise FocusLost(f"foreground window is {window}, not Minecraft; input stopped")
    return guard


def activate_window(find_window, user32=None):
    """Bring the game window forward. Windows may refuse while another app has the user's attention;
    client_checks.take_focus retries and the guard has the final word."""
    user32 = _user32() if user32 is None else user32
    hwnd = find_window()
    if not hwnd:
        raise FocusLost("Minecraft has no window to activate")
    if user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
