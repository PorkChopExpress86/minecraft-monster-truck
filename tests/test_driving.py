import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_node(script):
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


PRELUDE = r'''
import assert from 'node:assert/strict';
import { DRIVING, createDrivingState, headingVector, stepDriving } from './behavior_packs/MonsterTruck_BP/scripts/driving.js';
import { MAX_STEER_DEGREES } from './behavior_packs/MonsterTruck_BP/scripts/geometry.js';
const LEFT = 1, RIGHT = -1;
function drive(state, input, ticks, options = {}) {
  let result;
  for (let i = 0; i < ticks; i++) {
    result = stepDriving(state, input, options);
    state = result.state;
  }
  return result;
}
'''


def test_throttle_reaches_top_speed_coasts_brakes_and_reverses():
    run_node(PRELUDE + r'''
const start = createDrivingState(0);
const full = drive(start, { forward: 1 }, 40);
assert.equal(full.state.speed, DRIVING.topSpeed, "W reaches top speed in about 1.5 s");
assert.ok(drive(start, { forward: 1 }, 20).state.speed < DRIVING.topSpeed, "acceleration is gradual");
assert.deepEqual(full.velocity, { x: -0, z: DRIVING.topSpeed }, "yaw 0 drives toward +Z");

assert.equal(drive(full.state, {}, 40).state.speed, 0, "released W coasts to a stop in about 2 s");
assert.ok(drive(full.state, {}, 20).state.speed > 0, "coasting is gradual");

const braking = drive(full.state, { forward: -1 }, 5).state;
assert.ok(braking.speed > 0 && braking.speed < DRIVING.topSpeed - 0.3, "S brakes before reversing");
const reversing = drive(full.state, { forward: -1 }, 60).state;
assert.equal(reversing.speed, -DRIVING.reverseTopSpeed, "S reverses at a third of top speed once stopped");
''')


def test_a_and_d_turn_the_wheels_and_the_truck_only_while_moving():
    run_node(PRELUDE + r'''
const parked = drive(createDrivingState(0), { strafe: LEFT }, 20);
assert.equal(parked.state.steer, -MAX_STEER_DEGREES, "A turns the front wheels fully left");
assert.equal(parked.state.yaw, 0, "a parked truck does not spin in place");
assert.equal(drive(parked.state, {}, 20).state.steer, 0, "wheels spring back to center");

const cruising = drive(createDrivingState(0), { forward: 1 }, 40).state;
const left = drive(cruising, { forward: 1, strafe: LEFT }, 10).state;
const right = drive(cruising, { forward: 1, strafe: RIGHT }, 10).state;
assert.ok(left.yaw < 0 && right.yaw > 0, `A turns left (yaw down), D turns right: ${left.yaw}, ${right.yaw}`);

// Turning radius: wider at speed than at a crawl.
const slow = drive(createDrivingState(0), { forward: 0.3 }, 40).state;
const radius = state => {
  const next = stepDriving({ ...state, steer: -MAX_STEER_DEGREES }, { forward: state.speed / DRIVING.topSpeed, strafe: LEFT }).state;
  return Math.abs(state.speed / ((next.yaw - state.yaw) * Math.PI / 180));
};
assert.ok(radius(cruising) > 1.5 * radius(slow), `radius ${radius(cruising)} at speed vs ${radius(slow)} slow`);

const reverse = drive(createDrivingState(0), { forward: -1 }, 40).state;
assert.ok(drive(reverse, { forward: -1, strafe: LEFT }, 10).state.yaw > 0, "reversing with A swings the nose right");
''')


def test_handbrake_stops_hard_in_a_line_and_drifts_while_steering():
    run_node(PRELUDE + r'''
const cruising = drive(createDrivingState(0), { forward: 1 }, 40).state;
const stopped = drive(cruising, { handbrake: true }, 25).state;
assert.equal(stopped.speed, 0, "the handbrake stops the truck within about 1.1 s");
assert.equal(stopped.yaw, 0, "straight-line handbrake does not turn");
assert.equal(stopped.slip, 0);

const grip = drive(cruising, { forward: 1, strafe: RIGHT }, 10).state;
const drift = drive(cruising, { forward: 1, strafe: RIGHT, handbrake: true }, 10).state;
assert.ok(drift.yaw > grip.yaw, `the rear steps out: drift turns faster (${drift.yaw} vs ${grip.yaw})`);
assert.ok(Math.abs(drift.slip) > 10, "momentum keeps sliding the old way: " + drift.slip);
assert.ok(drift.sliding);
assert.equal(grip.slip, 0, "normal driving keeps full grip");

const recovered = drive(drift, { forward: 1 }, 12).state;
assert.equal(recovered.slip, 0, "grip returns within about half a second of release");
assert.equal(recovered.sliding, false);

const held = drive(createDrivingState(0), { forward: 1, handbrake: true }, 20).state;
assert.equal(held.speed, 0, "a parked truck with the handbrake held does not move");
''')


def test_blocked_truck_continues_from_measured_motion_and_has_no_air_control():
    run_node(PRELUDE + r'''
const cruising = drive(createDrivingState(0), { forward: 1 }, 40).state;
const blocked = stepDriving(cruising, { forward: 1 }, { measuredSpeed: 0 }).state;
assert.ok(blocked.speed <= DRIVING.acceleration, "a wall resets speed to what was achieved: " + blocked.speed);
assert.equal(stepDriving(cruising, { forward: 1 }, { measuredSpeed: 1.0 }).state.speed, DRIVING.topSpeed,
  "small measurement noise is ignored");

const airborne = stepDriving(cruising, { forward: -1, strafe: LEFT, handbrake: true }, { grounded: false });
assert.equal(airborne.state.speed, cruising.speed, "no throttle or brake in the air");
assert.equal(airborne.state.yaw, cruising.yaw, "no turning in the air");
assert.notEqual(airborne.state.steer, 0, "the wheels still turn visually");
const v = headingVector(90);
assert.ok(Math.abs(v.x + 1) < 1e-9 && Math.abs(v.z) < 1e-9, "yaw 90 faces -X");
''')


def test_ground_retention_uses_the_entity_friction_modifier():
    import json
    entity = json.loads((REPO_ROOT / "behavior_packs/MonsterTruck_BP/entities/monster_truck.entity.json").read_text())
    modifier = entity["minecraft:entity"]["components"]["minecraft:friction_modifier"]["value"]
    run_node(PRELUDE + f"""
import {{ groundRetention }} from './behavior_packs/MonsterTruck_BP/scripts/driving.js';
import {{ FRICTION_MODIFIER }} from './behavior_packs/MonsterTruck_BP/scripts/geometry.js';
assert.equal(FRICTION_MODIFIER, {modifier});
assert.ok(Math.abs(groundRetention("minecraft:grass_block") - 0.91 * 0.6 * {modifier}) < 1e-9);
assert.ok(groundRetention("minecraft:ice") > groundRetention("minecraft:stone"), "ice is slipperier");
assert.ok(groundRetention("minecraft:blue_ice") <= 1);
""")
