"""Client Input Run building blocks: uinput virtual input behind a focus guard (ADR-0019)."""
import struct

import pytest

from scripts import linux_input


class FakeDevice:
    def __init__(self):
        self.events = []

    def emit(self, etype, code, value):
        self.events.append((etype, code, value))

    def close(self):
        self.events.append("closed")


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_input(guard=lambda: None):
    clock = Clock()
    device = FakeDevice()
    return linux_input.VirtualInput(guard, device=device, clock=clock, sleep=clock.sleep), device, clock


def keys(events):
    """Key transitions only, as (key code, down)."""
    return [(code, value) for etype, code, value in (e for e in events if e != "closed") if etype == linux_input.EV_KEY]


def test_event_bytes_is_a_kernel_input_event():
    data = linux_input.event_bytes(linux_input.EV_KEY, 30, 1)
    assert len(data) == struct.calcsize("llHHi") == 24
    assert struct.unpack("llHHi", data)[2:] == (linux_input.EV_KEY, 30, 1)


def test_tap_checks_focus_then_presses_and_releases_with_a_sync_after_each():
    calls = []
    virtual, device, _ = make_input(guard=lambda: calls.append("guard"))
    virtual.tap("a")
    a = linux_input.KEYS["a"]
    assert calls == ["guard"]
    assert device.events == [(linux_input.EV_KEY, a, 1), (linux_input.EV_SYN, 0, 0),
                             (linux_input.EV_KEY, a, 0), (linux_input.EV_SYN, 0, 0)]


def test_typing_a_colon_holds_shift_around_semicolon():
    virtual, device, _ = make_input()
    virtual.type_text("1:")
    shift, semicolon, one = (linux_input.KEYS[k] for k in ("shift", ";", "1"))
    assert keys(device.events) == [(one, 1), (one, 0), (shift, 1), (semicolon, 1), (semicolon, 0), (shift, 0)]


def test_typing_a_character_without_a_key_is_refused_before_any_input():
    virtual, device, _ = make_input()
    with pytest.raises(ValueError, match="'@'"):
        virtual.type_text("a@")
    assert device.events == []


def test_hold_keeps_keys_down_for_the_duration_and_rechecks_focus():
    checks = []
    virtual, device, clock = make_input(guard=lambda: checks.append(clock.now))
    virtual.hold(["w", "a"], 1.0)
    w, a = linux_input.KEYS["w"], linux_input.KEYS["a"]
    assert keys(device.events) == [(w, 1), (a, 1), (w, 0), (a, 0)]
    assert clock.now == pytest.approx(1.0, abs=0.06)
    assert len(checks) >= 4, "focus is rechecked while keys are held"


def test_held_keys_go_down_together_after_one_focus_check():
    # A focus check takes a KWin round trip; one between W and Space would drive the truck on W alone.
    log = []
    virtual, device, _ = make_input(guard=lambda: log.append("guard"))
    device.emit = lambda etype, code, value: log.append((etype, code, value))
    virtual.hold(["w", "space"], 0.01)
    w, space = linux_input.KEYS["w"], linux_input.KEYS["space"]
    first_presses = log[:log.index((linux_input.EV_KEY, space, 1)) + 1]
    assert first_presses.count("guard") == 1 and first_presses[0] == "guard"
    assert (linux_input.EV_KEY, w, 1) in first_presses


def test_losing_focus_while_holding_releases_every_key_before_aborting():
    state = {"calls": 0}

    def guard():
        state["calls"] += 1
        if state["calls"] == 3:
            raise linux_input.FocusLost("active window is Konsole")

    virtual, device, _ = make_input(guard=guard)
    with pytest.raises(linux_input.FocusLost):
        virtual.hold(["w", "space"], 2.0)
    w, space = linux_input.KEYS["w"], linux_input.KEYS["space"]
    assert keys(device.events) == [(w, 1), (space, 1), (w, 0), (space, 0)], "no key is left pressed"


def test_on_tick_runs_during_a_hold_and_can_end_it_early():
    virtual, device, clock = make_input()
    seen = []
    virtual.hold(["w"], 5.0, on_tick=lambda: seen.append(clock.now) or len(seen) == 3)
    assert len(seen) == 3 and clock.now < 1.0
    assert keys(device.events)[-1] == (linux_input.KEYS["w"], 0)


def test_mouse_moves_in_steps_that_add_up_to_the_requested_distance():
    virtual, device, _ = make_input()
    virtual.move_mouse(301, -10, steps=4)
    moves = [(code, value) for etype, code, value in device.events if etype == linux_input.EV_REL]
    assert sum(v for c, v in moves if c == linux_input.REL_X) == 301
    assert sum(v for c, v in moves if c == linux_input.REL_Y) == -10
    assert len([1 for c, _ in moves if c == linux_input.REL_X]) == 4


def test_close_releases_held_keys_and_closes_the_device():
    virtual, device, _ = make_input()
    virtual.press("shift")
    virtual.close()
    assert keys(device.events)[-1] == (linux_input.KEYS["shift"], 0)
    assert device.events[-1] == "closed"


# ---------- WebSocket channel (Bedrock /connect) ----------

import base64  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import socket  # noqa: E402
import threading  # noqa: E402

from scripts import client_ws  # noqa: E402


class FakeMinecraft:
    """The client side of /connect: masked frames, as Bedrock sends them."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        key = base64.b64encode(os.urandom(16))
        self.sock.sendall(b"GET // HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                          b"Sec-WebSocket-Key: " + key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n")
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(1024)
        self.response = response.decode()
        self.key = key

    def recv_frame(self):
        b1, b2 = self._exact(2)
        assert not b2 & 0x80, "server frames are unmasked"
        length = b2 & 0x7F
        if length == 126:
            length = int.from_bytes(self._exact(2), "big")
        return b1, self._exact(length)

    def send(self, opcode, payload):
        mask = os.urandom(4)
        header = bytes([0x80 | opcode])
        header += bytes([0x80 | len(payload)]) if len(payload) < 126 else bytes([0x80 | 126]) + len(payload).to_bytes(2, "big")
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _exact(self, n):
        data = b""
        while len(data) < n:
            data += self.sock.recv(n - len(data))
        return data


@pytest.fixture
def channel():
    ws = client_ws.WsChannel(port=0)
    yield ws
    ws.close()


def test_handshake_accepts_the_client_key(channel):
    game = FakeMinecraft(channel.port)
    assert channel.wait_connected(2)
    import hashlib
    expected = base64.b64encode(hashlib.sha1(game.key + client_ws.GUID).digest()).decode()
    assert "101 Switching Protocols" in game.response and f"Sec-WebSocket-Accept: {expected}" in game.response


def test_command_returns_the_response_with_the_same_request_id(channel):
    game = FakeMinecraft(channel.port)
    channel.wait_connected(2)
    result = {}
    thread = threading.Thread(target=lambda: result.update(body=channel.command("querytarget @s")))
    thread.start()
    opcode, payload = game.recv_frame()
    request = json.loads(payload)
    assert opcode == 0x81 and request["body"]["commandLine"] == "querytarget @s"
    # An unrelated event first, then a long response (16-bit length) with the matching request id.
    game.send(1, json.dumps({"header": {"messagePurpose": "event", "eventName": "PlayerMessage"}, "body": {"message": "hi"}}).encode())
    game.send(1, json.dumps({"header": {"requestId": request["header"]["requestId"], "messagePurpose": "commandResponse"},
                             "body": {"statusCode": 0, "statusMessage": "x" * 300}}).encode())
    thread.join(3)
    assert result["body"]["statusMessage"] == "x" * 300
    assert [event["body"]["message"] for event in channel.events()] == ["hi"]


def test_ping_is_answered_with_pong(channel):
    game = FakeMinecraft(channel.port)
    channel.wait_connected(2)
    game.send(9, b"beat")
    assert game.recv_frame() == (0x8A, b"beat")


def test_unanswered_command_times_out(channel):
    game = FakeMinecraft(channel.port)  # kept alive: a collected socket would close the connection
    channel.wait_connected(2)
    with pytest.raises(client_ws.ChannelError, match="no response"):
        channel.command("say hi", timeout=0.2)


def test_command_before_any_connection_is_refused(channel):
    with pytest.raises(client_ws.ChannelError, match="not connected"):
        channel.command("say hi", timeout=0.2)


def test_query_target_details_are_parsed():
    body = {"statusCode": 0, "details": '[{"position": {"x": 1.5, "y": -60, "z": 3}, "yRot": -140.1, "uniqueId": "u"}]'}
    assert client_ws.query_targets(body) == [{"position": {"x": 1.5, "y": -60, "z": 3}, "yRot": -140.1, "uniqueId": "u"}]
    assert client_ws.query_targets({"statusCode": -2147352576, "statusMessage": "No targets matched selector"}) == []


def test_score_is_read_from_a_players_list_message():
    message = "§aShowing 2 tracked objective(s) for riding:\n- mt_probe: 1 (mt_probe)\n- other: 7 (other)"
    assert client_ws.score({"statusCode": 0, "statusMessage": message}, "mt_probe") == 1
    assert client_ws.score({"statusCode": 0, "statusMessage": message}, "missing") is None
    assert client_ws.score({"statusCode": -1, "statusMessage": "No such player"}, "mt_probe") is None


# ---------- focus guard and chat detection (bedrock_linux) ----------

from scripts import bedrock_linux as linux  # noqa: E402


def fake_kwin(monkeypatch, window):
    """KWin prints the active window to the user journal; journalctl --grep returns that line."""
    printed = {}

    def run_kwin_script(work_dir, name, source):
        printed["nonce"] = source.split('print("', 1)[1].split(" ", 1)[0]

    def run(argv, **kwargs):
        assert argv[:2] == ["journalctl", "--user"]
        return subprocess.CompletedProcess(argv, 0, stdout=f"{printed['nonce']} {json.dumps(window)}\n", stderr="")

    monkeypatch.setattr(linux, "run_kwin_script", run_kwin_script)
    monkeypatch.setattr(linux.subprocess, "run", run)


import subprocess  # noqa: E402


def test_active_window_reads_the_kwin_report_from_the_journal(monkeypatch, tmp_path):
    fake_kwin(monkeypatch, {"caption": "Minecraft", "pid": 4242})
    assert linux.active_window(tmp_path) == {"caption": "Minecraft", "pid": 4242}


def test_focus_guard_passes_only_for_the_launched_minecraft_window(monkeypatch, tmp_path):
    monkeypatch.setattr(linux, "process_group", lambda pgid: [(4242, "mcpelauncher-cli"), (4100, "bwrap")])
    guard = linux.focus_guard(tmp_path, type("P", (), {"pid": 4000})())
    fake_kwin(monkeypatch, {"caption": "Minecraft", "pid": 4242})
    guard()
    for window in ({"caption": "Konsole", "pid": 4242}, {"caption": "Minecraft", "pid": 999}, None):
        fake_kwin(monkeypatch, window)
        with pytest.raises(linux_input.FocusLost):
            guard()


def test_chat_screen_is_recognised_by_its_grey_title_bar(tmp_path):
    from PIL import Image
    chat = Image.new("RGB", (900, 600), (60, 90, 40))
    chat.paste((189, 189, 189), (0, 22, 900, 62))
    game = Image.new("RGB", (900, 600), (142, 185, 253))
    chat.save(tmp_path / "chat.png")
    game.save(tmp_path / "game.png")
    assert linux.chat_open(tmp_path / "chat.png")
    assert not linux.chat_open(tmp_path / "game.png")


# ---------- Client Input Run checks (client_checks) ----------

from scripts import client_checks  # noqa: E402


def test_yaw_delta_takes_the_short_way_round():
    assert client_checks.yaw_delta(170, -170) == pytest.approx(20)
    assert client_checks.yaw_delta(-170, 170) == pytest.approx(-20)
    assert client_checks.yaw_delta(10, -50) == pytest.approx(-60)


ORIGINAL_OPTIONS = ("gfx_fov:70\nwebsockets_enabled:0\nwebsocket_encryption:1\n"
                    "keyboard_type_0_key.sneak:16\nkeyboard_type_1_key.sneak:16\n")


def test_run_options_enable_websockets_and_rebind_sneak_then_restore_them(tmp_path):
    options = tmp_path / "options.txt"
    options.write_text(ORIGINAL_OPTIONS)
    with client_checks.run_options(options, tmp_path / "backup"):
        assert options.read_text() == ("gfx_fov:70\nwebsockets_enabled:1\nwebsocket_encryption:0\n"
                                       "keyboard_type_0_key.sneak:75\nkeyboard_type_1_key.sneak:75\n")
        # The game rewrites options.txt when it closes; its other changes survive the restore.
        options.write_text(options.read_text().replace("gfx_fov:70", "gfx_fov:90"))
    assert options.read_text() == ORIGINAL_OPTIONS.replace("gfx_fov:70", "gfx_fov:90")
    assert (tmp_path / "backup/options.txt").read_text() == ORIGINAL_OPTIONS


def test_run_options_missing_from_the_file_are_added_then_removed(tmp_path):
    options = tmp_path / "options.txt"
    options.write_text("gfx_fov:70\n")
    with client_checks.run_options(options, tmp_path / "backup"):
        assert "websockets_enabled:1\n" in options.read_text() and "keyboard_type_0_key.sneak:75\n" in options.read_text()
    assert options.read_text() == "gfx_fov:70\n"


class FakeInput:
    def __init__(self):
        self.actions = []

    def tap(self, key, hold=0.05):
        self.actions.append(("tap", key))

    def type_text(self, text):
        self.actions.append(("type", text))

    def hold(self, keys, seconds, on_tick=None):
        self.actions.append(("hold", tuple(keys), seconds))
        if on_tick:
            on_tick()

    def move_mouse(self, dx, dy, steps=10, interval=0.02):
        self.actions.append(("mouse", dx, dy))


class FakeConnectChannel:
    port = 19131

    def __init__(self, connects):
        self.connects = connects

    def wait_connected(self, timeout):
        return self.connects


def test_connect_opens_chat_focuses_the_box_then_types_connect():
    keys = FakeInput()
    screens = iter([False, True, True])  # chat appears on the second capture, still open after Enter
    client_checks.connect_client(keys, FakeConnectChannel(True), chat_visible=lambda: next(screens),
                                 sleep=lambda s: None)
    assert keys.actions == [("tap", "/"), ("tap", "enter"), ("type", "connect 127.0.0.1:19131"), ("tap", "enter")]


def test_connect_types_nothing_when_the_chat_never_opens():
    keys = FakeInput()
    with pytest.raises(client_checks.ClientInputError, match="chat"):
        client_checks.connect_client(keys, FakeConnectChannel(True), chat_visible=lambda: False, sleep=lambda s: None,
                                     attempts=2)
    assert ("type", "connect 127.0.0.1:19131") not in keys.actions
    assert keys.actions.count(("tap", "/")) == 2


class World:
    """A fake real-client world behind the channel: the truck turns with the held keys."""

    def __init__(self, turn_per_key=None, lost=0, riding_after_sneak=0, mouse_turns_truck=0.0):
        self.truck = {"x": 0.5, "z": 3.5, "yaw": 0.0}
        self.player_yaw = 0.0
        self.riding = 1
        self.lost = lost
        self.turn = turn_per_key or {"a": -40.0, "d": 40.0}
        self.riding_after_sneak = riding_after_sneak
        self.mouse_turns_truck = mouse_turns_truck
        self.commands = []

    def command(self, line, timeout=5.0):
        self.commands.append(line)
        if line.startswith("querytarget @e"):
            t = self.truck
            return {"statusCode": 0, "details": json.dumps([{"position": {"x": t["x"], "y": -60, "z": t["z"]}, "yRot": t["yaw"]}])}
        if line.startswith("querytarget @s"):
            return {"statusCode": 0, "details": json.dumps([{"position": {"x": 0, "y": -60, "z": 0}, "yRot": self.player_yaw}])}
        if line == "scoreboard players list riding":
            return {"statusCode": 0, "statusMessage": f"- mt_probe: {self.riding} (mt_probe)"}
        if line == "scoreboard players list lost":
            return {"statusCode": 0, "statusMessage": f"- mt_probe: {self.lost} (mt_probe)"}
        return {"statusCode": 0, "statusMessage": "ok"}


class WorldInput(FakeInput):
    def __init__(self, world):
        super().__init__()
        self.world = world

    def hold(self, keys, seconds, on_tick=None):
        super().hold(keys, seconds, on_tick)
        if "w" in keys and "space" not in keys:
            self.world.truck["z"] += 1.1 * 20 * seconds
        for key in keys:
            self.world.truck["yaw"] += self.world.turn.get(key, 0.0) * seconds
        if client_checks.SNEAK_KEY in keys:
            self.world.riding = self.world.riding_after_sneak

    def move_mouse(self, dx, dy, steps=10, interval=0.02):
        super().move_mouse(dx, dy, steps, interval)
        self.world.player_yaw += dx / 10
        self.world.truck["yaw"] += self.world.mouse_turns_truck


def run_check(name, world):
    ctx = client_checks.Context(world, WorldInput(world), base=(0, -60, 0), sleep=lambda s: None)
    return client_checks.CHECKS[name](ctx)


def test_a_must_turn_left_and_d_right():
    assert run_check("a_turns_left", World())
    with pytest.raises(client_checks.CheckFailed, match="A turned the truck \\+"):
        run_check("a_turns_left", World(turn_per_key={"a": 40.0, "d": -40.0}))
    with pytest.raises(client_checks.CheckFailed, match="D turned"):
        run_check("d_turns_right", World(turn_per_key={"a": 40.0, "d": -40.0}))


def test_space_fails_if_the_rider_left_the_seat_for_even_one_tick():
    assert run_check("space_keeps_rider", World())
    with pytest.raises(client_checks.CheckFailed, match="out of the seat for 2 ticks"):
        run_check("space_keeps_rider", World(lost=2))


def test_sneak_must_dismount():
    assert run_check("sneak_dismounts", World(riding_after_sneak=0))
    with pytest.raises(client_checks.CheckFailed, match="still in seat 1"):
        run_check("sneak_dismounts", World(riding_after_sneak=1))


def test_focus_is_taken_before_the_first_key_with_a_few_activation_attempts():
    calls = {"activate": 0, "guard": 0}

    def guard():
        calls["guard"] += 1
        if calls["guard"] < 3:
            raise linux_input.FocusLost("Claude is active")

    client_checks.take_focus(lambda: calls.__setitem__("activate", calls["activate"] + 1), guard, sleep=lambda s: None)
    assert calls == {"activate": 3, "guard": 3}


def test_a_desktop_that_never_gives_minecraft_focus_blocks_the_run():
    def guard():
        raise linux_input.FocusLost("Claude is active")

    with pytest.raises(client_checks.ClientInputError, match="leave the desktop idle"):
        client_checks.take_focus(lambda: None, guard, attempts=2, sleep=lambda s: None)
