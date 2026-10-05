"""Client Input Run (ADR-0019): the real Linux client, driven by a virtual keyboard and mouse.

The run deploys the add-on with the harness in probe mode to the Dedicated Test World, turns the client's
WebSocket options on for its own duration, launches the client, and joins it to a local WebSocket server by
typing `/connect` into chat. Each check then presses real keys while reading the client's own world over
that channel: querytarget for positions and facing, the harness probe's scoreboard for who rides what.
Every key and mouse event passes the focus guard first (bedrock_linux.focus_guard).
"""
import contextlib
import math
from pathlib import Path
import re
import shutil
import time

try:
    from . import bedrock_linux as linux
    from .bedrock_client import await_client_load
    from .bedrock_world import SetupError, bootstrap, dedicated_pack_ids, deploy
    from .client_ws import ChannelError, WsChannel, query_targets, score
    from .linux_input import FocusLost, VirtualInput
except ImportError:
    import bedrock_linux as linux
    from bedrock_client import await_client_load
    from bedrock_world import SetupError, bootstrap, dedicated_pack_ids, deploy
    from client_ws import ChannelError, WsChannel, query_targets, score
    from linux_input import FocusLost, VirtualInput

PROBE = "mt_probe"  # testing/harness/client_probe.js
# A virtual Shift never reaches the launcher as Sneak (real Shift does), so for the run Sneak is rebound to K,
# a key nothing else uses; the check then exercises the Sneak action itself (ADR-0019).
SNEAK_KEY, SNEAK_KEY_CODE = "k", "75"
RUN_OPTIONS = {"websockets_enabled": "1", "websocket_encryption": "0",
               "keyboard_type_0_key.sneak": SNEAK_KEY_CODE, "keyboard_type_1_key.sneak": SNEAK_KEY_CODE}


class ClientInputError(Exception):
    """The run could not set up or reach the client (not a failed check)."""


class CheckFailed(Exception):
    pass


def yaw_delta(before, after):
    """Signed change in facing, in degrees, the short way round (Bedrock yaw: 0 faces +Z, A turns it negative)."""
    return (after - before + 180) % 360 - 180


@contextlib.contextmanager
def run_options(options, backup_dir):
    """For the run only: let the client join an unencrypted local WebSocket, and bind Sneak to SNEAK_KEY.

    The game rewrites options.txt when it closes, so the restore resets just these keys to what they were
    (removing any that were absent) and keeps the game's other changes. A full copy is kept in backup_dir.
    """
    options = Path(options)
    original = options.read_text(encoding="utf-8")
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy2(options, Path(backup_dir) / "options.txt")
    before = {}
    text = original
    for key, value in RUN_OPTIONS.items():
        match = re.search(rf"(?m)^{re.escape(key)}:(.*)$", text)
        before[key] = match.group(1) if match else None
        if match:
            text = text[:match.start(1)] + value + text[match.end(1):]
        else:
            text += ("" if text.endswith("\n") or not text else "\n") + f"{key}:{value}\n"
    options.write_text(text, encoding="utf-8")
    try:
        yield
    finally:
        text = options.read_text(encoding="utf-8")
        for key, value in before.items():
            if value is None:
                text = re.sub(rf"(?m)^{re.escape(key)}:.*\n?", "", text)
            else:
                text = re.sub(rf"(?m)^{re.escape(key)}:.*$", lambda _: f"{key}:{value}", text)
        options.write_text(text, encoding="utf-8")


def connect_client(keys, channel, chat_visible, sleep=time.sleep, attempts=3):
    """Type `/connect` into the client's chat. '/' opens chat with "/" prefilled but the box unfocused; Enter
    focuses it; typed text then lands in the box, and Enter sends. Nothing is typed unless the chat screen is
    seen, since keys typed in the game itself would act as controls."""
    for _ in range(attempts):
        keys.tap("/")
        if not any(chat_visible() or sleep(0.4) for _ in range(20)):
            continue
        sleep(1.0)
        keys.tap("enter")
        sleep(1.0)
        if not chat_visible():
            continue
        keys.type_text(f"connect 127.0.0.1:{channel.port}")
        sleep(0.5)
        keys.tap("enter")
        if channel.wait_connected(10):
            return
    raise ClientInputError(f"Could not connect the client through the chat screen in {attempts} attempts")


def take_focus(activate, guard, attempts=5, sleep=time.sleep):
    """Give Minecraft keyboard focus before the first key. KWin can refuse an activation while someone is
    using another window; after the first key, losing focus aborts the run instead (linux_input)."""
    for _ in range(attempts):
        activate()
        sleep(1.0)
        try:
            guard()
            return
        except FocusLost:
            continue
    raise ClientInputError("Minecraft could not take keyboard focus; leave the desktop idle during a Client Input Run")


class Context:
    def __init__(self, ws, keys, base, entity="blake:monster_truck", sleep=time.sleep):
        self.ws = ws
        self.keys = keys
        self.base = base
        self.entity = entity
        self.sleep = sleep

    def run(self, line, must_succeed=True):
        body = self.ws.command(line)
        if must_succeed and body.get("statusCode") != 0:
            raise ClientInputError(f"{line!r} failed: {body.get('statusMessage')}")
        return body

    def truck(self):
        targets = query_targets(self.run(f"querytarget @e[type={self.entity},c=1]", must_succeed=False))
        if not targets:
            raise CheckFailed("the truck is gone")
        return targets[0]["position"], targets[0]["yRot"]

    def player_yaw(self):
        return query_targets(self.run("querytarget @s"))[0]["yRot"]

    def probe(self, name):
        value = score(self.run(f"scoreboard players list {name}", must_succeed=False), PROBE)
        if value is None:
            raise ClientInputError(f"The harness probe published no {name!r} score; is the probe pack loaded?")
        return value

    def fresh_truck(self):
        """A new truck at the arena start, facing +Z, with the player seated in the Driver Seat."""
        bx, by, bz = self.base
        self.run("ride @s stop_riding", must_succeed=False)
        self.run(f"kill @e[type={self.entity}]", must_succeed=False)
        self.run("kill @e[type=item]", must_succeed=False)
        self.run(f"tp @s {bx + 0.5} {by} {bz + 0.5} 0 0")
        # The client's summon takes no rotation (that overload needs an experiment), so tp sets the facing.
        self.run(f"summon {self.entity} {bx + 0.5} {by} {bz + 3.5}")
        self.run(f"tp @e[type={self.entity}] {bx + 0.5} {by} {bz + 3.5} 0 0")
        self.sleep(0.5)
        self.run(f"ride @s start_riding @e[type={self.entity},c=1] teleport_rider")
        for _ in range(30):
            if self.probe("riding") == 1:
                break
            self.sleep(0.1)
        else:
            raise ClientInputError("The player never took the Driver Seat after /ride")
        self.sleep(1.0)
        self.run(f"scoreboard players set lost {PROBE} 0")


def w_drives(ctx):
    ctx.fresh_truck()
    start, _ = ctx.truck()
    ctx.keys.hold(["w"], 1.5)
    end, _ = ctx.truck()
    ahead, aside = end["z"] - start["z"], end["x"] - start["x"]
    if ahead < 3 or abs(aside) > 1:
        raise CheckFailed(f"W moved the truck {ahead:+.2f} blocks ahead and {aside:+.2f} aside in 1.5 s")
    return f"W drove the truck {ahead:.1f} blocks straight ahead in 1.5 s"


def _turn(ctx, key):
    ctx.fresh_truck()
    ctx.keys.hold(["w"], 0.8)
    _, before = ctx.truck()
    ctx.keys.hold(["w", key], 1.2)
    _, after = ctx.truck()
    return yaw_delta(before, after)


def a_turns_left(ctx):
    turned = _turn(ctx, "a")
    if turned > -15:
        raise CheckFailed(f"A turned the truck {turned:+.1f} degrees (left is negative, at least 15)")
    return f"A while driving turned the truck {turned:+.1f} degrees (left)"


def d_turns_right(ctx):
    turned = _turn(ctx, "d")
    if turned < 15:
        raise CheckFailed(f"D turned the truck {turned:+.1f} degrees (right is positive, at least 15)")
    return f"D while driving turned the truck {turned:+.1f} degrees (right)"


def space_keeps_rider(ctx):
    ctx.fresh_truck()
    ctx.keys.hold(["w"], 1.0)
    ctx.keys.hold(["w", "space"], 2.0)  # handbrake from speed
    stopped, _ = ctx.truck()
    ctx.keys.hold(["w", "space"], 1.0)  # held handbrake against W
    held, _ = ctx.truck()
    creep = math.hypot(held["x"] - stopped["x"], held["z"] - stopped["z"])
    for _ in range(5):
        ctx.keys.tap("space", hold=0.1)
        ctx.sleep(0.15)
    ctx.keys.hold(["space"], 2.0)
    lost, riding = ctx.probe("lost"), ctx.probe("riding")
    if lost or riding != 1:
        raise CheckFailed(f"Space put the player out of the seat for {lost} ticks (riding {riding})")
    if creep > 0.3:
        raise CheckFailed(f"with Space held the truck crept {creep:.2f} blocks under W")
    return (f"Space while driving, held against W ({creep:.2f} blocks creep), tapped 5 times and held 2 s parked: "
            "the player was in the Driver Seat on every tick the probe saw")


def sneak_dismounts(ctx):
    ctx.fresh_truck()
    ctx.keys.hold([SNEAK_KEY], 0.6)
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"after Sneak the player is still in seat {riding}")
    ctx.sleep(1.0)  # an engine detachment would be undone within the 8-tick retention window
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"Sneak got the player out, but the add-on put them back in seat {riding}")
    return "Sneak got the player out of the truck, and they stayed out"


CHECKS = {check.__name__: check for check in
          (w_drives, a_turns_left, d_turns_right, space_keeps_rider, sneak_dismounts)}


def select_checks(only):
    if only is None:
        return list(CHECKS)
    names = [name.strip() for name in only.split(",") if name.strip()]
    unknown = [name for name in names if name not in CHECKS]
    if not names or unknown:
        raise SetupError("Unknown client check; choose from: " + ", ".join(CHECKS))
    return [name for name in CHECKS if name in names]


def run_client_input(root, config, run_id, output, only=None):
    """Deploy, launch, connect, run the checks, close; returns the report stage."""
    names = select_checks(only)
    client_dir = output / "client-input"
    client_dir.mkdir(parents=True, exist_ok=True)
    launcher_client = linux_client()
    local = bootstrap(root, config, launcher_client)
    world = Path(local["world"]).absolute()
    deploy(root, config, world, run_id, client_probe=True)
    options = linux.data_dir() / "games/com.mojang/minecraftpe/options.txt"
    results, errors = [], []
    with run_options(options, client_dir / "options-backup"):
        process = linux.launch(world.name, config["linux_client_version"], output / "client-stdout.log")
        keys = channel = None
        try:
            load = await_client_load(process, output / "client-stdout.log", world,
                                     (dedicated_pack_ids(config)[0], config["harness_uuid"]),
                                     {**config, "observe_seconds": 0})
            if load["status"] != "passed":
                raise ClientInputError("; ".join(load["errors"]))
            time.sleep(8)  # the world finishes loading chunks and UI after the player spawns
            guard = linux.focus_guard(client_dir, process)
            take_focus(lambda: linux.activate_window(client_dir), guard)
            keys = VirtualInput(guard)
            channel = WsChannel()
            frames = client_dir / "frames"
            frames.mkdir(exist_ok=True)
            connect_client(keys, channel, lambda: linux.chat_open(linux.capture(frames)))
            channel.subscribe("PlayerMessage")
            ctx = Context(channel, keys, base=None, entity=config["entity_id"])
            me = query_targets(ctx.run("querytarget @s"))[0]["position"]
            ctx.base = (math.floor(me["x"]), math.floor(me["y"]), math.floor(me["z"]))
            prepare_arena(ctx)
            for name in names:
                started = time.monotonic()
                entry = {"name": name}
                try:
                    entry.update(status="passed", detail=CHECKS[name](ctx))
                except CheckFailed as error:
                    entry.update(status="failed", error=str(error))
                entry["seconds"] = round(time.monotonic() - started, 1)
                shot = client_dir / name
                shot.mkdir(exist_ok=True)
                with contextlib.suppress(Exception):
                    entry["screenshot"] = linux.capture(shot)
                results.append(entry)
                print(f"Client check {name}: {entry['status'].upper()} {entry.get('detail') or entry.get('error')}", flush=True)
        except (ClientInputError, ChannelError, FocusLost, linux.ClientError) as error:
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            for closer in (lambda: keys and keys.close(), lambda: channel and channel.close()):
                with contextlib.suppress(Exception):
                    closer()
            try:
                linux.close(process, client_dir)
            except linux.ClientError as error:
                errors.append(str(error))
    failed = errors or len(results) != len(names) or any(entry["status"] != "passed" for entry in results)
    return {"status": "failed" if failed else "passed", "checks": results, "errors": errors}


def prepare_arena(ctx):
    """Daylight, no weather or mobs, nothing left from earlier runs, and a flat clear strip along +Z."""
    bx, by, bz = ctx.base
    for line in ("time set day", "weather clear", "gamerule domobspawning false", "gamerule dodaylightcycle false",
                 "kill @e[type=!player]",
                 f"fill {bx - 25} {by - 1} {bz - 10} {bx + 25} {by - 1} {bz + 55} grass_block",
                 f"fill {bx - 25} {by} {bz - 10} {bx + 25} {by + 8} {bz + 55} air"):
        body = ctx.run(line, must_succeed=False)
        # kill with no targets and a fill that changes nothing ("0 blocks filled") are not setup failures.
        if body.get("statusCode") != 0 and not line.startswith(("kill", "fill")):
            raise ClientInputError(f"{line!r} failed: {body.get('statusMessage')}")


def linux_client():
    if __package__:
        from .bedrock_client import LauncherClient
    else:
        from bedrock_client import LauncherClient
    return LauncherClient()
