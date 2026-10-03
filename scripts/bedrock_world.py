"""The Dedicated Test World: create it from Mojang's pinned MIT-licensed starter, claim it for this
repository (configure/bootstrap), and deploy the add-on plus the test-only harness into it."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import urllib.request
import uuid
import zipfile

try:
    from .addon_packs import AddonPacks, com_mojang_roots, read_json, write_json
except ImportError:
    from addon_packs import AddonPacks, com_mojang_roots, read_json, write_json


WORLD_URL = (
    "https://raw.githubusercontent.com/Mojang/minecraft-creator-tools/"
    "3edc61769233fc6f7c4bb1028c03f465a379523c/app/public/data/content/flatcreativegt.mcworld"
)
WORLD_SHA256 = "b8f1fc6423b88a7010f2ab851b0386d4bef34bc36a80489e9c13870c12f6c328"
SOURCE_MARKER = ".addon-test-world-source.json"
OWNER = ".addon-test-owner.json"


class SetupError(Exception):
    """The local test environment blocks a run (exit code 2): world, client, or configuration."""


def account_root():
    candidates = com_mojang_roots(require_options=True)
    if len(candidates) != 1:
        raise ValueError("Automatic setup requires one initialized Minecraft account; use Configure for multiple accounts")
    return candidates[0]


def enable_logging(root, data_root):
    options = data_root / "minecraftpe/options.txt"
    if options.resolve() != options.absolute():
        raise ValueError("Refusing redirected Minecraft settings file")
    original = options.read_bytes()
    match = re.search(rb"(?m)^content_log_file:([01])(?=\r?$)", original)
    if not match:
        if re.search(rb"(?m)^content_log_file:", original):
            raise ValueError("Installed Minecraft options contain a malformed content_log_file setting")
        backup = root / "dist/bedrock-tests/setup" / uuid.uuid4().hex / "options.txt"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        newline = b"\r\n" if b"\r\n" in original else b"\n"
        separator = b"" if not original or original.endswith((b"\n", b"\r")) else newline
        options.write_bytes(original + separator + b"content_log_file:1" + newline)
    elif match[1] == b"0":
        backup = root / "dist/bedrock-tests/setup" / uuid.uuid4().hex / "options.txt"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        options.write_bytes(original[:match.start(1)] + b"1" + original[match.end(1):])
    if "mcpelauncher" in data_root.parts:
        logs = data_root / "logs"
    elif "Packages" in data_root.parts:
        logs = data_root.parent.parent / "logs"
    else:
        logs = Path(os.environ["APPDATA"]) / "Minecraft Bedrock/logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs.resolve()


def template_bytes(root):
    cached = root / "dist/bedrock-tests/cache/flatcreativegt.mcworld"
    if not cached.exists():
        with urllib.request.urlopen(WORLD_URL, timeout=30) as response:
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("World starter exceeds the expected size limit")
    else:
        data = cached.read_bytes()
    if hashlib.sha256(data).hexdigest() != WORLD_SHA256:
        raise ValueError("World starter SHA-256 mismatch; refusing to extract")
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def customize_level(data, name, beta_apis=False):
    import nbtlib  # only world creation needs it; doctor and the --dry-run shim must not
    version, size = struct.unpack("<II", data[:8])
    if size != len(data) - 8:
        raise ValueError("World level.dat length does not match its header")
    level = nbtlib.File.parse(io.BytesIO(data[8:]), byteorder="little")
    level["LevelName"] = nbtlib.String(name)
    for key, value in {
        "GameType": 1, "Difficulty": 0, "commandsEnabled": 1,
        "MultiplayerGame": 0, "MultiplayerGameIntent": 0,
        "LANBroadcast": 0, "LANBroadcastIntent": 0,
        "XBLBroadcastIntent": 0, "PlatformBroadcastIntent": 0,
    }.items():
        level[key] = type(level[key])(value)
    # The old starter enabled experimental GameTest; stable Script API needs none.
    # Only the headless Scenario World turns "Beta APIs" (key gametest) back on (ADR-0016).
    for key in level["experiments"]:
        level["experiments"][key] = nbtlib.Byte(0)
    if beta_apis:
        level["experiments"]["gametest"] = nbtlib.Byte(1)
    stream = io.BytesIO()
    level.write(stream, byteorder="little")
    payload = stream.getvalue()
    return struct.pack("<II", version, len(payload)) + payload


def check_archive(archive, label, max_file_size=None):
    """Refuse a zip whose members could land outside the extraction directory (or are oversized) before extracting."""
    for item in archive.infolist():
        path = Path(item.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
            raise ValueError("Unsafe path in " + label)
        if max_file_size is not None and item.file_size > max_file_size:
            raise ValueError("Unexpectedly large file in " + label)


def create_world(root, config, data_root=None):
    root = Path(root).resolve()
    data_root = Path(data_root).resolve() if data_root else account_root()
    worlds = data_root / "minecraftWorlds"
    if worlds.resolve() != worlds.absolute():
        raise ValueError("Refusing redirected minecraftWorlds directory")
    worlds.mkdir(parents=True, exist_ok=True)
    world = worlds / ("addon-test-" + str(uuid.UUID(config["harness_uuid"])))
    provenance = {"repository": str(root), "harness_uuid": config["harness_uuid"],
                  "source_url": WORLD_URL, "sha256": WORLD_SHA256}
    if world.exists():
        marker = world / SOURCE_MARKER
        if world.resolve() != world.absolute() or not marker.is_file() or json.loads(marker.read_text()) != provenance:
            raise ValueError("World destination already exists and is not this runner's generated world")
        if not (world / "level.dat").is_file():
            raise ValueError("Generated world is incomplete; refusing to replace it")
    else:
        data = template_bytes(root)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            check_archive(archive, "world starter", max_file_size=10_000_000)
            with tempfile.TemporaryDirectory(prefix=".addon-world-", dir=worlds) as staging:
                stage = Path(staging)
                if not stage.resolve().is_relative_to(worlds.resolve()):
                    raise ValueError("World staging directory escaped its parent")
                archive.extractall(stage)
                name = config["name"] + " Automated Tests"
                level = customize_level((stage / "level.dat").read_bytes(), name)
                (stage / "level.dat").write_bytes(level)
                (stage / "level.dat_old").write_bytes(level)
                (stage / "levelname.txt").write_text(name, encoding="utf-8")
                (stage / SOURCE_MARKER).write_text(json.dumps(provenance, indent=2), encoding="utf-8")
                shutil.copy2(root / "testing/world-template.LICENSE.txt", stage / "world-template.LICENSE.txt")
                # The final directory is new; never overlay or delete an existing world.
                stage.rename(world)
    logs = enable_logging(root, data_root)
    return {"world": str(world), "log_directory": str(logs)}


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


def dedicated_pack_ids(config):
    namespace = uuid.UUID(config["harness_uuid"])
    return str(uuid.uuid5(namespace, "behavior-pack")), str(uuid.uuid5(namespace, "resource-pack"))


def deploy(root, config, world, run_id):
    validate_world(world)
    owner = checked_destination(world, OWNER)
    if not owner.exists() or read_json(owner) != owner_data(root, config):
        raise SetupError("World ownership is not configured for this repository")
    packs = AddonPacks.load(root, config)
    bp, rp = packs.bp.manifest, packs.rp.manifest
    test_bp_id, test_rp_id = dedicated_pack_ids(config)
    for name, allowed in (
        ("world_behavior_packs.json", {bp["header"]["uuid"], test_bp_id, config["harness_uuid"]}),
        ("world_resource_packs.json", {rp["header"]["uuid"], test_rp_id}),
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
            {"uuid": test_bp_id, "version": bp["header"]["version"]},
        ],
    })
    run = {"run_id": run_id, "entity_id": config["entity_id"],
           "required_components": config.get("required_components", []),
           "showcase": config.get("showcase", False)}
    if "expected_seat_count" in config:
        run["expected_seat_count"] = config["expected_seat_count"]
    packs.stage_test_pack(world, destinations[0], destinations[1], run, harness / "scripts/run_config.js",
                          pack_ids=(test_bp_id, test_rp_id),
                          extra_behavior_packs=[{"pack_id": config["harness_uuid"], "version": [1, 0, 0]}])


def configure(root, config, world, logs, client):
    """Claim a fresh world for this repository and deploy into it; client (bedrock_client) must be closed."""
    client.assert_closed()
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


def bootstrap(root, config, client):
    """Create or refresh the Dedicated Test World named by testing/bedrock.local.json; client must be closed."""
    client.assert_closed()
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
            configure(root, config, local["world"], local["log_directory"], client)
    except ValueError as error:
        raise SetupError(str(error)) from error
    print("Automatic world setup ready: " + local["world"], flush=True)
    return local
