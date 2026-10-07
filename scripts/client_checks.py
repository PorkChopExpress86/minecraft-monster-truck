"""Client Input Run (ADR-0019): the real Linux client, driven by a virtual keyboard and mouse.

The run deploys the add-on with the harness in probe mode to the Dedicated Test World, turns the client's
WebSocket options on for its own duration, launches the client, and joins it to a local WebSocket server by
typing `/connect` into chat. Each check then presses real keys while reading the client's own world over
that channel: querytarget for positions and facing, the harness probe's scoreboard for who rides what.
Every key and mouse event passes the focus guard first (bedrock_linux.focus_guard).
"""
import contextlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys
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
# Probe scores a traced run (--trace) samples while keys are held, for diagnosing a failed check.
TRACE_SCORES = ("riding", "lost", "sneaking", "sneak_button", "jump")
# How far sneak_during_drop drops the truck: about 1.4 s of fall on the real client (--diag run 81a440e5),
# long enough for a focus check of the Sneak hold, each with two queries (about one every 0.6 s, runs
# 9d4bbbd3 and 42808732), to see the truck still in the air.
DROP_HEIGHT = 32
# The Sixteen-Color Palette in the entity's paint-event order (blake:paint_<color>), for palette_screenshots.
PALETTE = tuple(event.removeprefix("blake:paint_") for event in json.loads(
    (Path(__file__).resolve().parents[1] / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json")
    .read_text(encoding="utf-8"))["minecraft:entity"]["events"] if event.startswith("blake:paint_"))
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
    def __init__(self, ws, keys, base, entity="blake:monster_truck", sleep=time.sleep, trace=False,
                 clock=time.monotonic, capture=None):
        self.ws = ws
        self.keys = keys
        self.base = base
        self.entity = entity
        self.sleep = sleep
        self.trace = trace
        self.clock = clock
        self.samples = []
        self.started = clock()
        self.capture = capture  # name -> path of a screenshot of the client, saved under client-input/<name>/

    def hold(self, keys, seconds, until=None):
        """Hold keys for `seconds`, or until until() is true at a focus check of the hold; when tracing, sample
        every probe score at each check (about 1.5 a second: each sample is one WebSocket query per score)."""
        def tick():
            if self.trace:
                self._sample(keys)
            return bool(until and until())
        self.keys.hold(keys, seconds, on_tick=tick if self.trace or until else None)

    def _sample(self, keys):
        self.samples.append({"t": round(self.clock() - self.started, 2), "keys": list(keys),
                             **{name: self.probe(name) for name in TRACE_SCORES}})
        return False

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

    def fresh_truck(self, at=(0.5, 3.5), up=0):
        """A new truck at arena offset `at` (x, z; default the start) and `up` blocks above the arena floor,
        facing +Z, with the player in the Driver Seat."""
        bx, by, bz = self.base
        tx, tz = bx + at[0], bz + at[1]
        ty = by + up
        self.run("ride @s stop_riding", must_succeed=False)
        self.run(f"kill @e[type={self.entity}]", must_succeed=False)
        self.run("kill @e[type=item]", must_succeed=False)
        self.run(f"tp @s {bx + 0.5} {by} {bz + 0.5} 0 0")
        # The client's summon takes no rotation (that overload needs an experiment), so tp sets the facing.
        self.run(f"summon {self.entity} {tx} {ty} {tz}")
        self.run(f"tp @e[type={self.entity}] {tx} {ty} {tz} 0 0")
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
    ctx.hold(["w"], 1.5)
    end, _ = ctx.truck()
    ahead, aside = end["z"] - start["z"], end["x"] - start["x"]
    if ahead < 3 or abs(aside) > 1:
        raise CheckFailed(f"W moved the truck {ahead:+.2f} blocks ahead and {aside:+.2f} aside in 1.5 s")
    return f"W drove the truck {ahead:.1f} blocks straight ahead in 1.5 s"


def _turn(ctx, key):
    ctx.fresh_truck()
    ctx.hold(["w"], 0.8)
    _, before = ctx.truck()
    ctx.hold(["w", key], 1.2)
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
    ctx.hold(["w"], 1.0)
    ctx.hold(["w", "space"], 2.0)  # handbrake from speed
    stopped, _ = ctx.truck()
    ctx.hold(["w", "space"], 1.0)  # held handbrake against W
    held, _ = ctx.truck()
    creep = math.hypot(held["x"] - stopped["x"], held["z"] - stopped["z"])
    for _ in range(5):
        ctx.keys.tap("space", hold=0.1)
        ctx.sleep(0.15)
    ctx.hold(["space"], 2.0)
    lost, riding = ctx.probe("lost"), ctx.probe("riding")
    if lost or riding != 1:
        raise CheckFailed(f"Space put the player out of the seat for {lost} ticks (riding {riding})")
    if creep > 0.3:
        raise CheckFailed(f"with Space held the truck crept {creep:.2f} blocks under W")
    return (f"Space while driving, held against W ({creep:.2f} blocks creep), tapped 5 times and held 2 s parked: "
            "the player was in the Driver Seat on every tick the probe saw")


def sneak_dismounts(ctx):
    ctx.fresh_truck()
    ctx.hold([SNEAK_KEY], 0.6)
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"after Sneak the player is still in seat {riding}")
    ctx.sleep(1.0)  # an engine detachment would be undone within the 8-tick retention window
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"Sneak got the player out, but the add-on put them back in seat {riding}")
    # Seated players have Jump off so Space cannot dismount them (#40); on foot it must be back on.
    if ctx.run("inputpermission query @s jump enabled", must_succeed=False).get("statusCode") != 0:
        raise CheckFailed("Sneak got the player out, but their Jump is still off")
    return "Sneak got the player out of the truck, they stayed out, and Jump works again"


def space_sneak_exits(ctx):
    ctx.fresh_truck()
    ctx.hold(["space"], 0.5)  # the handbrake held, then Sneak with it still down
    ctx.hold(["space", SNEAK_KEY], 0.6)
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"with Space held, Sneak left the player still in seat {riding}")
    ctx.sleep(1.0)
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"with Space held, Sneak got the player out, but the add-on put them back in seat {riding}")
    return "With the handbrake held, Sneak got the player out of the truck, and they stayed out"


def s_brakes_and_reverses(ctx):
    ctx.fresh_truck()
    ctx.hold(["w"], 1.0)
    start, before = ctx.truck()
    # From about 0.7 blocks/tick, S brakes to a stop in about half a second, then reverses: about 6 blocks
    # behind where S was pressed after 2.5 s (DRIVING in driving.js).
    ctx.hold(["s"], 2.5)
    end, after = ctx.truck()
    back, aside = end["z"] - start["z"], end["x"] - start["x"]
    if back > -2:
        raise CheckFailed(f"S moved the truck {back:+.2f} blocks along its heading in 2.5 s (braking then "
                          "reversing ends at least 2 blocks behind)")
    turned = yaw_delta(before, after)
    if abs(turned) > 10 or abs(aside) > 1:
        raise CheckFailed(f"S turned the truck {turned:+.1f} degrees and moved it {aside:+.2f} blocks aside")
    return f"S braked, then reversed the truck {-back:.1f} blocks straight back in 2.5 s"


def sneak_exits_afloat(ctx):
    # A pool behind the start, clear of the other checks' paths: stone floor, 4 blocks of water up to the grass.
    bx, by, bz = ctx.base
    ctx.run(f"fill {bx - 3} {by - 5} {bz - 9} {bx + 3} {by - 5} {bz - 4} stone", must_succeed=False)
    ctx.run(f"fill {bx - 3} {by - 4} {bz - 9} {bx + 3} {by - 1} {bz - 4} water", must_succeed=False)
    ctx.fresh_truck(at=(0.5, -6.5))
    ctx.sleep(2.0)  # the truck settles afloat
    truck, _ = ctx.truck()
    ctx.hold([SNEAK_KEY], 0.6)
    riding = ctx.probe("riding")
    if riding != 0:
        raise CheckFailed(f"Sneak afloat left the player still in seat {riding}")
    ctx.sleep(0.5)
    player = query_targets(ctx.run("querytarget @s"))[0]["position"]
    # Over liquid the add-on sets a Sneak exit down on the nearest dry land (amphibious.js findDryLanding):
    # here the grass around the pool, whose top is at the base height.
    if player["y"] < by - 0.1:
        raise CheckFailed(f"Sneak afloat dropped into the water: the player is {player['y'] - by:+.2f} blocks from "
                          "the pool's grass edge")
    off = math.hypot(player["x"] - truck["x"], player["z"] - truck["z"])
    return f"Sneak afloat set the player down on the pool's edge, {off:.1f} blocks from the truck"


def sneak_stays_seated_over_lava(ctx):
    # A lava pool off to the side of the start, wider than the add-on's reach for dry land (amphibious.js
    # DRY_LAND_REACH, 4 blocks) on every side of the truck at its middle; filled in again afterwards.
    bx, by, bz = ctx.base
    pool = f"{bx - 24} {by - 4} {bz - 10} {bx - 10} {by - 1} {bz + 4}"
    ctx.run(f"fill {pool} lava", must_succeed=False)
    try:
        ctx.fresh_truck(at=(-16.5, -2.5))
        ctx.sleep(2.0)  # the truck settles afloat (still and seated by then: run 025c4272)
        ctx.hold([SNEAK_KEY], 0.6)
        ctx.sleep(1.0)
        riding = ctx.probe("riding")
        if riding != 1:
            raise CheckFailed(f"Sneak over lava with no land in reach put the player out of the Driver Seat (seat {riding})")
        lost = ctx.probe("lost")
        # Control: with dry footing 3 blocks to the truck's side (stone at the lava surface), the same Sneak must
        # get the player out onto it; otherwise the seated result could be a Sneak that never reached the game.
        truck, _ = ctx.truck()
        fx, fz = math.floor(truck["x"]) + 3, math.floor(truck["z"])
        ctx.run(f"fill {fx} {by - 1} {fz - 1} {fx + 1} {by - 1} {fz + 1} stone")
        ctx.hold([SNEAK_KEY], 0.6)
        ctx.sleep(0.5)
        riding = ctx.probe("riding")
        if riding != 0:
            raise CheckFailed(f"with dry land 3 blocks away, Sneak over lava still left the player in seat {riding}: "
                              "the Sneak key may never have reached the game, so the seated result proves nothing")
    finally:
        ctx.run("ride @s stop_riding", must_succeed=False)
        ctx.run(f"tp @s {bx + 0.5} {by} {bz + 0.5}", must_succeed=False)
        ctx.run(f"fill {pool} grass_block", must_succeed=False)
    return (f"Sneak over lava with no land in reach left the player in the Driver Seat ({lost} ticks out by the probe); "
            "with dry land 3 blocks away the same Sneak got them out")


def sneak_during_drop(ctx):
    # The truck stands on a floating stone platform; removing it drops the truck straight down onto the start
    # strip, from rest, with the player seated (driving off a ledge spends the short fall on reaching it).
    bx, by, bz = ctx.base
    platform = f"{bx - 3} {by + DROP_HEIGHT - 1} {bz + 1} {bx + 3} {by + DROP_HEIGHT - 1} {bz + 6}"
    ctx.run(f"fill {platform} stone", must_succeed=False)
    try:
        ctx.fresh_truck(up=DROP_HEIGHT)
        ctx.run(f"fill {platform} air")
        top = by + DROP_HEIGHT
        # Sneak goes down once the drop is under way, not as the floor goes (a Sneak on steady ground exits).
        for _ in range(40):
            if ctx.truck()[0]["y"] < top - 1:
                break
            ctx.sleep(0.05)
        else:
            raise CheckFailed("the truck never started to fall after its platform was removed")
        seats = []  # (seat, truck y) at each focus check of the hold

        def record_seat_until_landed():
            seats.append((ctx.probe("riding"), ctx.truck()[0]["y"]))
            return seats[-1][1] <= by + 0.1
        ctx.hold([SNEAK_KEY], 4.0, until=record_seat_until_landed)
        if ctx.truck()[0]["y"] > by + 0.1:
            raise CheckFailed("the truck never landed in 4 s of Sneak")
        if any(seat != 1 for seat, _ in seats):
            raise CheckFailed(f"Sneak during the drop put the player out of the seat (seat, truck y: {seats})")
        lost = ctx.probe("lost")  # every tick since fresh_truck seated the player, between the samples too
        if lost:
            raise CheckFailed(f"Sneak during the drop put the player out of the seat for {lost} ticks")
        heights = [round(y - by, 1) for _, y in seats if y > by + 0.1]
        if not heights:
            raise CheckFailed("Sneak was held, but no focus check saw the truck still in the air; the drop proves nothing")
        ctx.sleep(1.0)  # past the 8-tick landing window (landing.js RIDER_RETENTION_TICKS)
        riding = ctx.probe("riding")
        if riding != 1:
            raise CheckFailed(f"after landing the player is in seat {riding}, not the Driver Seat")
        ctx.hold([SNEAK_KEY], 0.6)
        riding = ctx.probe("riding")
        if riding != 0:
            raise CheckFailed(f"after landing, Sneak left the player in seat {riding}")
        ctx.sleep(1.0)
        riding = ctx.probe("riding")
        if riding != 0:
            raise CheckFailed(f"after landing, Sneak got the player out, but the add-on put them back in seat {riding}")
    finally:
        ctx.run(f"fill {platform} air", must_succeed=False)
    return (f"Sneak held through a {DROP_HEIGHT}-block drop kept the player in the Driver Seat: on every "
            f"tick the probe saw to the landing (sampled at {heights} blocks up); then Sneak got them out")


def palette_screenshots(ctx):
    """Not a judgement of looks: paints one parked truck each palette color and screenshots it from the same
    spot, front three-quarter view, for a person (or Claude) to compare body, hood and wheel-hub accents."""
    bx, by, bz = ctx.base
    tx, tz = bx + 0.5, bz + 3.5
    ctx.run("ride @s stop_riding", must_succeed=False)
    ctx.run(f"kill @e[type={ctx.entity}]", must_succeed=False)
    ctx.run(f"summon {ctx.entity} {tx} {by} {tz}")
    ctx.run(f"tp @e[type={ctx.entity}] {tx} {by} {tz} 0 0")
    # A fixed free camera, so the player's own view mode (first or third person) never puts them in the shot.
    ctx.run(f"camera @s set minecraft:free pos {tx + 4} {by + 2.5} {tz + 5} facing {tx} {by + 1} {tz}")
    shots = {}
    try:
        for color in PALETTE:
            body = ctx.run(f"event entity @e[type={ctx.entity}] blake:paint_{color}", must_succeed=False)
            if body.get("statusCode") != 0:
                raise CheckFailed(f"the truck refused paint event {color}: {body.get('statusMessage')}")
            ctx.sleep(0.5)  # the property reaches the client and the textures swap (all 16 shown: run 7c7025f5)
            shots[color] = str(ctx.capture(f"palette/{color}"))
    finally:
        ctx.run("camera @s clear", must_succeed=False)
    return f"{len(shots)} palette colors screenshotted for review: " + json.dumps(shots)


CHECKS = {check.__name__: check for check in
          (w_drives, a_turns_left, d_turns_right, s_brakes_and_reverses, space_keeps_rider, sneak_dismounts,
           space_sneak_exits, sneak_exits_afloat, sneak_stays_seated_over_lava, sneak_during_drop, palette_screenshots)}


def select_checks(only, checks=None):
    checks = CHECKS if checks is None else checks
    if only is None:
        return list(checks)
    names = [name.strip() for name in only.split(",") if name.strip()]
    unknown = [name for name in names if name not in checks]
    if not names or unknown:
        raise SetupError("Unknown client check; choose from: " + ", ".join(checks))
    return [name for name in checks if name in names]


def load_diag(path):
    """A diagnostic file's CHECKS ({name: check(ctx) -> detail}), run in place of the built-in checks
    (--diag). It may import `scripts.client_checks` for Context helpers; a check's returned detail, such as
    a JSON dump of what it measured, lands in report.json."""
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(f"client_diag_{Path(path).stem}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (OSError, SyntaxError) as error:
        raise SetupError(f"Could not load the diagnostic file {path}: {error}") from error
    checks = getattr(module, "CHECKS", None)
    if not isinstance(checks, dict) or not checks:
        raise SetupError(f"{path} defines no CHECKS dict of name -> check(ctx)")
    return checks


def run_client_input(root, config, run_id, output, only=None, trace=False, diag=None):
    """Deploy, launch, connect, run the checks (or a --diag file's), close; returns the report stage."""
    checks = load_diag(diag) if diag else CHECKS
    names = select_checks(only, checks)
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
            ctx = Context(channel, keys, base=None, entity=config["entity_id"], trace=trace,
                          capture=lambda name: linux.capture(mkdir(client_dir / name)))
            me = query_targets(ctx.run("querytarget @s"))[0]["position"]
            ctx.base = (math.floor(me["x"]), math.floor(me["y"]), math.floor(me["z"]))
            prepare_arena(ctx)
            for name in names:
                started = time.monotonic()
                entry = {"name": name}
                ctx.samples, ctx.started = [], started
                try:
                    entry.update(status="passed", detail=checks[name](ctx))
                except CheckFailed as error:
                    entry.update(status="failed", error=str(error))
                entry["seconds"] = round(time.monotonic() - started, 1)
                if trace:
                    entry["trace"] = ctx.samples
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


def mkdir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def linux_client():
    if __package__:
        from .bedrock_client import LauncherClient
    else:
        from bedrock_client import LauncherClient
    return LauncherClient()
