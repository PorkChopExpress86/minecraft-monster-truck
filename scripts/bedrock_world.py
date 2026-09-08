"""Create an isolated local test world from Mojang's pinned MIT-licensed starter."""
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

import nbtlib


WORLD_URL = (
    "https://raw.githubusercontent.com/Mojang/minecraft-creator-tools/"
    "3edc61769233fc6f7c4bb1028c03f465a379523c/app/public/data/content/flatcreativegt.mcworld"
)
WORLD_SHA256 = "b8f1fc6423b88a7010f2ab851b0386d4bef34bc36a80489e9c13870c12f6c328"
SOURCE_MARKER = ".addon-test-world-source.json"


def account_root():
    users = Path(os.environ["APPDATA"]) / "Minecraft Bedrock/Users"
    candidates = [path for path in users.glob("*/games/com.mojang")
                  if path.parents[1].name != "Shared" and (path / "minecraftpe/options.txt").is_file()]
    legacy = (Path(os.environ["LOCALAPPDATA"]) /
              "Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang")
    if not candidates and (legacy / "minecraftpe/options.txt").is_file():
        candidates = [legacy]
    if len(candidates) != 1:
        raise ValueError("Automatic setup requires one initialized Minecraft account; use Configure for multiple accounts")
    return candidates[0].resolve()


def enable_logging(root, data_root):
    options = data_root / "minecraftpe/options.txt"
    if options.resolve() != options.absolute():
        raise ValueError("Refusing redirected Minecraft settings file")
    original = options.read_bytes()
    match = re.search(rb"(?m)^content_log_file:([01])(?=\r?$)", original)
    if not match:
        raise ValueError("Installed Minecraft options do not expose the known content_log_file setting")
    if match[1] == b"0":
        backup = root / "dist/bedrock-tests/setup" / uuid.uuid4().hex / "options.txt"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(original)
        options.write_bytes(original[:match.start(1)] + b"1" + original[match.end(1):])
    if "Packages" in data_root.parts:
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


def customize_level(data, name):
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
    for key in level["experiments"]:
        level["experiments"][key] = nbtlib.Byte(0)
    stream = io.BytesIO()
    level.write(stream, byteorder="little")
    payload = stream.getvalue()
    return struct.pack("<II", version, len(payload)) + payload


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
            for item in archive.infolist():
                path = Path(item.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in item.filename:
                    raise ValueError("Unsafe path in world starter")
                if item.file_size > 10_000_000:
                    raise ValueError("Unexpectedly large file in world starter")
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
