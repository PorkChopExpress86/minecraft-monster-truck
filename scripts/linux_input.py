"""Virtual keyboard and mouse for the Client Input Run (ADR-0019): a user-level uinput device.

Every press goes through a focus guard first. Keys reach whichever window has focus, so a guard that finds
another window active aborts the run, and every key still held is released before the abort propagates.
"""
import fcntl
import os
import struct
import time

EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y = 0, 1
BTN_LEFT, BTN_RIGHT = 0x110, 0x111
# <linux/uinput.h>: UI_SET_EVBIT/KEYBIT/RELBIT = _IOW('U', 100..102, int); UI_DEV_SETUP = _IOW('U', 3, uinput_setup).
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x5501, 0x5502
BUS_VIRTUAL = 0x06

# Linux key codes (<linux/input-event-codes.h>) for a US layout, which this desktop uses.
KEYS = {
    **dict(zip("1234567890", range(2, 12))),
    **dict(zip("qwertyuiop", range(16, 26))),
    **dict(zip("asdfghjkl", range(30, 39))),
    **dict(zip("zxcvbnm", range(44, 51))),
    "esc": 1, "-": 12, "enter": 28, ";": 39, "shift": 42, ",": 51, ".": 52, "/": 53, "space": 57, " ": 57,
}
SHIFTED = {":": ";", "_": "-"}
GUARD_INTERVAL = 0.25  # seconds between focus checks while keys are held


class FocusLost(Exception):
    """Another window took focus; input stops before it can reach that window."""


def event_bytes(etype, code, value):
    """One struct input_event (zero timestamp: the kernel stamps uinput events)."""
    return struct.pack("llHHi", 0, 0, etype, code, value)


class UinputDevice:
    """A virtual keyboard plus relative mouse. /dev/uinput carries a uaccess ACL for the seat user, so no root."""

    def __init__(self, name=b"monster-truck-client-input"):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            for etype in (EV_KEY, EV_REL):
                fcntl.ioctl(self.fd, UI_SET_EVBIT, etype)
            for code in sorted(set(KEYS.values()) | {BTN_LEFT, BTN_RIGHT}):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for code in (REL_X, REL_Y):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, code)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, struct.pack("HHHH80sI", BUS_VIRTUAL, 0x4D54, 0x0001, 1, name, 0))
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise
        time.sleep(1.0)  # the compositor must add the new device before its first event counts

    def emit(self, etype, code, value):
        os.write(self.fd, event_bytes(etype, code, value))

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)


class VirtualInput:
    def __init__(self, guard, device=None, clock=time.monotonic, sleep=time.sleep):
        self.guard = guard
        self.device = UinputDevice() if device is None else device
        self.clock = clock
        self.sleep = sleep
        self.held = []

    def _key(self, code, down):
        self.device.emit(EV_KEY, code, 1 if down else 0)
        self.device.emit(EV_SYN, 0, 0)

    def press(self, key, guarded=True):
        if guarded:
            self.guard()
        self._key(KEYS[key], True)
        self.held.append(key)

    def release(self, key):
        self._key(KEYS[key], False)
        self.held.remove(key)

    def release_all(self):
        while self.held:
            self.release(self.held[0])

    def tap(self, key, hold=0.05):
        self.press(key)
        self.sleep(hold)
        self.release(key)
        self.sleep(0.05)

    def type_text(self, text):
        unknown = [ch for ch in text if ch not in KEYS and ch not in SHIFTED]
        if unknown:
            raise ValueError(f"No key for {unknown[0]!r}")
        for ch in text:
            if ch in SHIFTED:
                self.press("shift")
                self.tap(SHIFTED[ch])
                self.release("shift")
            else:
                self.tap(ch)

    def hold(self, keys, seconds, on_tick=None):
        """Hold keys for seconds, rechecking focus; on_tick() runs between checks and may return True to stop."""
        try:
            # One focus check, then every key at once: a check between them would hold the first alone.
            self.guard()
            for key in keys:
                self.press(key, guarded=False)
            end = self.clock() + seconds
            while self.clock() < end:
                self.sleep(min(GUARD_INTERVAL, max(end - self.clock(), 0)))
                self.guard()
                if on_tick and on_tick():
                    break
        finally:
            for key in keys:
                if key in self.held:
                    self.release(key)

    def move_mouse(self, dx, dy, steps=10, interval=0.02):
        self.guard()
        for step in range(steps):
            # Integer steps whose sum is exactly (dx, dy).
            sx = dx * (step + 1) // steps - dx * step // steps
            sy = dy * (step + 1) // steps - dy * step // steps
            self.device.emit(EV_REL, REL_X, sx)
            self.device.emit(EV_REL, REL_Y, sy)
            self.device.emit(EV_SYN, 0, 0)
            self.sleep(interval)

    def close(self):
        try:
            self.release_all()
        finally:
            self.device.close()
