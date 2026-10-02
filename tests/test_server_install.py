"""Tests for opt-in deployment to Docker Bedrock Dedicated Server containers."""
import json
import subprocess
from pathlib import Path

import pytest

from scripts.install_addon import install_to_server
from scripts.version_manager import BP_UUID, RP_UUID

REPO_ROOT = Path(__file__).resolve().parent.parent
BP_SRC = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP"
RP_SRC = REPO_ROOT / "resource_packs" / "MonsterTruck_RP"
WORLD = "/data/worlds/Survival World"


class FakeDocker:
    """Records docker calls against an in-memory container filesystem."""

    def __init__(self, files):
        self.files = dict(files)
        self.calls = []

    def __call__(self, *args, input=None):
        self.calls.append(args)
        ok = lambda out="": subprocess.CompletedProcess(args, 0, out, "")
        if args[0] == "exec" and args[2] == "cat":
            path = args[3]
            if path in self.files:
                return ok(self.files[path])
            return subprocess.CompletedProcess(args, 1, "", f"cat: {path}: No such file")
        if args[0] == "exec" and args[1] == "-i":
            self.files[args[-1]] = input
            return ok()
        if args[0] == "exec" and args[2] == "sed":
            path = args[-1]
            self.files[path] = self.files[path].replace("texturepack-required=false", "texturepack-required=true")
        return ok()


def make_docker(properties="level-name=Survival World\ntexturepack-required=true\n"):
    other = [{"pack_id": "607de414-3833-44b6-ba45-81457be8303a", "version": [1, 0, 1]}]
    return FakeDocker({
        "/data/server.properties": properties,
        f"{WORLD}/world_behavior_packs.json": json.dumps(other + [{"pack_id": BP_UUID, "version": [1, 0, 0]}]),
    })


def test_install_to_server_activates_packs_and_restarts_on_yes():
    docker = make_docker()

    install_to_server("survival", [1, 0, 3], BP_SRC, RP_SRC, run=docker, confirm=lambda _: "y")

    behavior = json.loads(docker.files[f"{WORLD}/world_behavior_packs.json"])
    resource = json.loads(docker.files[f"{WORLD}/world_resource_packs.json"])
    assert behavior[0]["pack_id"] == "607de414-3833-44b6-ba45-81457be8303a"
    assert behavior[1] == {"pack_id": BP_UUID, "version": [1, 0, 3]}
    assert resource == [{"pack_id": RP_UUID, "version": [1, 0, 3]}]
    assert ("cp", f"{BP_SRC}/.", "minecraft-survival:/data/behavior_packs/MonsterTruck_BP") in docker.calls
    assert ("cp", f"{RP_SRC}/.", "minecraft-survival:/data/resource_packs/MonsterTruck_RP") in docker.calls
    assert docker.calls[-1] == ("restart", "minecraft-survival")


def test_install_to_server_skips_restart_without_confirmation_and_requires_texture_pack():
    docker = make_docker("level-name=Survival World\ntexturepack-required=false\n")

    install_to_server("survival", [1, 0, 3], BP_SRC, RP_SRC, run=docker, confirm=lambda _: "")

    assert "texturepack-required=true" in docker.files["/data/server.properties"]
    assert ("restart", "minecraft-survival") not in docker.calls


def test_install_to_server_rejects_missing_level_name():
    docker = FakeDocker({"/data/server.properties": "gamemode=survival\n"})

    with pytest.raises(RuntimeError, match="level-name"):
        install_to_server("survival", [1, 0, 3], BP_SRC, RP_SRC, run=docker, confirm=lambda _: "y")
    assert not any(call[0] == "cp" for call in docker.calls)
