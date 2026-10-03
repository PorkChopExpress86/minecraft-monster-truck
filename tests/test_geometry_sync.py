import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GEOMETRY = "./behavior_packs/MonsterTruck_BP/scripts/geometry.js"


def load_geometry():
    """Import geometry.js in node and return its exports as a dict."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")
    script = (
        f"const g = await import('{GEOMETRY}');"
        "process.stdout.write(JSON.stringify({ ...g }));"
    )
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_geometry_matches_config_entity_and_resource_pack():
    g = load_geometry()
    config = json.loads((REPO_ROOT / "vehicle.config.json").read_text(encoding="utf-8"))
    entity = json.loads((REPO_ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json")
                        .read_text(encoding="utf-8"))["minecraft:entity"]
    components = entity["components"]
    properties = entity["description"]["properties"]
    animations = json.loads((REPO_ROOT / "resource_packs/MonsterTruck_RP/animations/monster_truck.animation.json")
                            .read_text(encoding="utf-8"))

    # Body width: config, collision box, and the trample footprint agree.
    assert g["TRUCK_WIDTH"] == config["vehicle"]["collision_width_blocks"]
    assert g["TRUCK_WIDTH"] == components["minecraft:collision_box"]["width"]

    # Ground friction the driving model divides by is the entity's own modifier.
    assert g["FRICTION_MODIFIER"] == config["vehicle"]["friction_modifier"]
    assert g["FRICTION_MODIFIER"] == components["minecraft:friction_modifier"]["value"]

    # Angle limits match the synced entity properties' ranges.
    assert properties["blake:steer_angle"]["range"] == [-g["MAX_STEER_DEGREES"], g["MAX_STEER_DEGREES"]]
    assert properties["blake:pitch_angle"]["range"] == [-g["MAX_PITCH_DEGREES"], g["MAX_PITCH_DEGREES"]]

    # Coordinated Four-Wheel Steering: the RP rear wheels counter-steer by REAR_STEER_RATIO,
    # 18 degrees at full 26-degree lock.
    bones = animations["animations"]["animation.blake.monster_truck.steer"]["bones"]
    for bone in ("steer_rl", "steer_rr"):
        expr = bones[bone]["rotation"][1]
        match = re.fullmatch(r"-query\.property\('blake:steer_angle'\) \* ([0-9.]+)", expr)
        assert match, f"{bone} rotation is not a counter-steer ratio: {expr}"
        assert float(match.group(1)) == round(g["REAR_STEER_RATIO"], 4)
    assert round(g["MAX_STEER_DEGREES"] * g["REAR_STEER_RATIO"]) == 18

    # Pitch samples ground one axle offset ahead of and behind the centre.
    assert g["AXLE_OFFSET"] * 2 == g["PITCH_AXLE_SPAN"]
