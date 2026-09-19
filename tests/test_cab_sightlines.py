"""Automated first-person view and cab interior sightline clearance tests."""
import json
import math
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_seat_configuration_and_ground_driving_authority():
    bp_entity_path = REPO_ROOT / "behavior_packs" / "MonsterTruck_BP" / "entities" / "monster_truck.entity.json"
    assert bp_entity_path.exists()
    data = json.loads(bp_entity_path.read_text(encoding="utf-8"))
    comps = data["minecraft:entity"]["components"]

    # 1. Ground driving authority must be present for WASD keyboard control
    assert "minecraft:input_ground_controlled" in comps, "Must have minecraft:input_ground_controlled for WASD driving"
    assert "minecraft:can_power_jump" not in comps, "Native charged jumping must not overlap script-owned Suspension Jump"

    # 2. Rideable seats
    rideable = comps["minecraft:rideable"]
    assert rideable["seat_count"] == 2
    assert rideable["controlling_seat"] == 0

    seats = rideable["seats"]
    assert len(seats) == 2

    # Driver Seat (Seat 0): front-left side [0.45, 1.15, 0.15]
    driver_seat = seats[0]
    assert driver_seat["position"] == [0.45, 1.15, 0.15], "Driver seat must be at [0.45, 1.15, 0.15] on the front-left door"
    assert driver_seat["third_person_camera_radius"] == 7.5

    # Passenger Seat (Seat 1): front-right side [-0.45, 1.15, 0.15]
    passenger_seat = seats[1]
    assert passenger_seat["position"] == [-0.45, 1.15, 0.15], "Passenger seat must be at [-0.45, 1.15, 0.15] on the front-right door"
    assert passenger_seat["third_person_camera_radius"] == 7.5

def test_first_person_cab_interior_sightlines_and_headroom():
    geo_path = REPO_ROOT / "resource_packs" / "MonsterTruck_RP" / "models" / "entity" / "monster_truck.geo.json"
    assert geo_path.exists()
    data = json.loads(geo_path.read_text(encoding="utf-8"))

    geom = data["minecraft:geometry"][0]
    body_bone = next(b for b in geom["bones"] if b["name"] == "body")
    cubes = body_bone["cubes"]

    # Locate roof cube: elevated roof over cab
    roof_cubes = [
        c for c in cubes
        if c["origin"][1] >= 44 and c["size"][0] >= 20 and c["size"][2] >= 15
    ]
    assert len(roof_cubes) >= 1, "Must find elevated cab roof cube"
    roof = roof_cubes[0]
    roof_bottom_y = roof["origin"][1]
    assert roof_bottom_y >= 46.0, f"Roof underside must be at least Y=46.0 to avoid clipping, got {roof_bottom_y}"

    # Locate windshield opening
    glass_cubes = [
        c for c in cubes
        if "glass" in str(c.get("uv", "")) or (c["size"][0] >= 20 and c["size"][2] <= 1 and c["origin"][2] < 0)
    ]
    assert len(glass_cubes) >= 1, "Must find front windshield glass cube"
    windshield = glass_cubes[0]
    ws_bottom_y = windshield["origin"][1]
    ws_top_y = ws_bottom_y + windshield["size"][1]

    # Driver seated eye position in model units (1 block = 16 units)
    # Seat coordinate: [0.45, 1.15, 0.15] blocks -> [7.2, 18.4, 2.4] units
    # Seated rider eye height: ~1.4 blocks = 22.4 units above seat pivot
    seat_x = 0.45 * 16.0  # 7.2 units (left side)
    seat_y = 1.15 * 16.0  # 18.4 units
    seat_z = 0.15 * 16.0  # 2.4 units
    eye_x = seat_x
    eye_y = seat_y + 22.4 # 40.8 units
    eye_z = seat_z        # 2.4 units

    # 1. Verify vertical eye position is centered inside transparent windshield
    assert ws_bottom_y <= eye_y <= ws_top_y, (
        f"Driver eye height Y={eye_y:.1f} must sit inside windshield vertical span "
        f"[{ws_bottom_y}, {ws_top_y}]"
    )

    # 2. Headroom verification: distance from eye height to roof underside
    headroom = roof_bottom_y - eye_y
    assert headroom >= 5.0, f"Must have at least 5.0 units of headroom below roof, got {headroom:.1f}"

    # 3. Raycast line-of-sight test through windshield at pitch 0, -15 deg, +15 deg
    dist_to_ws = eye_z - windshield["origin"][2] # from 2.4 to -8.5 = 10.9 units
    for pitch_deg in [0, -15, 15]:
        pitch_rad = math.radians(pitch_deg)
        target_y = eye_y + dist_to_ws * math.tan(pitch_rad)

        # Check ray enters windshield opening
        assert ws_bottom_y <= target_y <= ws_top_y, (
            f"Line of sight at {pitch_deg} deg hits Y={target_y:.1f}, outside windshield "
            f"[{ws_bottom_y}, {ws_top_y}]"
        )
        # Check ray does not strike solid roof
        assert target_y < roof_bottom_y, (
            f"Line of sight at {pitch_deg} deg intersects cab roof at Y={target_y:.1f}"
        )
