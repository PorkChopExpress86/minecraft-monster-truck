import io
import json
from pathlib import Path
import struct
import zipfile

import nbtlib
import pytest

from scripts import bedrock_world as world


@pytest.fixture
def starter(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "testing").mkdir(parents=True)
    (root / "testing/world-template.LICENSE.txt").write_text("Fixture license")
    data_root = tmp_path / "account/games/com.mojang"
    options = data_root / "minecraftpe/options.txt"
    options.parent.mkdir(parents=True)
    options.write_bytes(b"other_setting:keep\r\ncontent_log_file:0\r\n")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config = {"name": "Fixture Cart", "harness_uuid": "18835304-6819-4c3c-bfcb-93b26b93d996"}
    level = nbtlib.File({
        "LevelName": nbtlib.String("starter"),
        "GameType": nbtlib.Int(0), "Difficulty": nbtlib.Int(2),
        "experiments": nbtlib.Compound({"gametest": nbtlib.Byte(1)}),
        **{key: nbtlib.Byte(1) for key in (
            "commandsEnabled", "MultiplayerGame", "MultiplayerGameIntent", "LANBroadcast",
            "LANBroadcastIntent", "XBLBroadcastIntent", "PlatformBroadcastIntent")},
    })
    payload = io.BytesIO()
    level.write(payload, byteorder="little")
    data = struct.pack("<II", 9, len(payload.getvalue())) + payload.getvalue()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("level.dat", data)
        zipped.writestr("db/CURRENT", b"fixture database")
    monkeypatch.setattr(world, "template_bytes", lambda _: archive.getvalue())
    return root, data_root, config, options


def test_world_creation_is_automatic_isolated_and_repeatable(starter):
    root, data_root, config, options = starter
    result = world.create_world(root, config, data_root)
    target = Path(result["world"])
    level_bytes = (target / "level.dat").read_bytes()
    level = nbtlib.File.parse(io.BytesIO(level_bytes[8:]), byteorder="little")
    assert level["LevelName"] == "Fixture Cart Automated Tests"
    assert level["GameType"] == 1 and level["Difficulty"] == 0
    assert level["MultiplayerGame"] == 0 and level["experiments"]["gametest"] == 0
    assert (target / "db/CURRENT").read_bytes() == b"fixture database"
    assert options.read_bytes() == b"other_setting:keep\r\ncontent_log_file:1\r\n"
    backups = list((root / "dist/bedrock-tests/setup").glob("*/options.txt"))
    assert len(backups) == 1 and b"content_log_file:0" in backups[0].read_bytes()
    (target / "keep.txt").write_text("existing test world state")
    assert world.create_world(root, config, data_root) == result
    assert (target / "keep.txt").read_text() == "existing test world state"
    assert len(list((root / "dist/bedrock-tests/setup").glob("*/options.txt"))) == 1


def test_world_creation_refuses_existing_unowned_destination(starter):
    root, data_root, config, _ = starter
    target = data_root / "minecraftWorlds" / ("addon-test-" + config["harness_uuid"])
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("personal world")
    with pytest.raises(ValueError, match="already exists"):
        world.create_world(root, config, data_root)
    assert (target / "keep.txt").read_text() == "personal world"


def test_archive_traversal_is_rejected_before_extracting(starter, monkeypatch):
    root, data_root, config, _ = starter
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../escaped.txt", "bad")
    monkeypatch.setattr(world, "template_bytes", lambda _: archive.getvalue())
    with pytest.raises(ValueError, match="Unsafe path"):
        world.create_world(root, config, data_root)
    assert not (data_root / "escaped.txt").exists()


def test_cached_template_hash_is_verified(tmp_path):
    cached = tmp_path / "dist/bedrock-tests/cache/flatcreativegt.mcworld"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"wrong template")
    with pytest.raises(ValueError, match="SHA-256"):
        world.template_bytes(tmp_path)


def test_unknown_logging_setting_preserves_options(starter):
    root, data_root, _, options = starter
    options.write_text("unknown_setting:1\n")
    with pytest.raises(ValueError, match="known content_log_file"):
        world.enable_logging(root, data_root)
    assert options.read_text() == "unknown_setting:1\n"
