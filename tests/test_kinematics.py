import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_kinematics_pitch_and_steering_contracts():
    node_exe = shutil.which("node")
    if not node_exe:
        return

    script = r'''
import assert from 'node:assert/strict';
import {
  calculateDynamicPitch,
  calculateSteerAngle,
  calculateRearSteerAngle,
  MAX_PITCH_DEGREES,
  MAX_STEER_DEGREES,
  REAR_STEER_RATIO
} from './behavior_packs/MonsterTruck_BP/scripts/kinematics.js';

// 1. Constants check
assert.equal(MAX_PITCH_DEGREES, 35);
assert.equal(MAX_STEER_DEGREES, 26);
assert.ok(Math.abs(REAR_STEER_RATIO - (18.0 / 26.0)) < 0.01);

// 2. Dynamic Incline Pitch: Ground climbing and descending
const wheelbase = 2.25;

// Climbing 1 block over wheelbase (front height 65, rear height 64)
const climbPitch = calculateDynamicPitch({
  frontHeight: 65.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 0.0,
  isAirborne: false,
  inLiquid: false,
  verticalVelocity: 0.0,
  smoothingFactor: 1.0 // 1.0 = instant target for testing
});
assert.ok(climbPitch > 20 && climbPitch <= 35, `Climbing pitch should be positive and <= 35, got ${climbPitch}`);

// Steep 2-block cliff auto-step (front height 66, rear height 64) - must clamp to MAX_PITCH_DEGREES (35)
const maxClimbPitch = calculateDynamicPitch({
  frontHeight: 66.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 0.0,
  isAirborne: false,
  inLiquid: false,
  verticalVelocity: 0.0,
  smoothingFactor: 1.0
});
assert.equal(maxClimbPitch, 35, `Climb pitch must clamp to 35, got ${maxClimbPitch}`);

// Descending 1 block (front height 63, rear height 64)
const descendPitch = calculateDynamicPitch({
  frontHeight: 63.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 0.0,
  isAirborne: false,
  inLiquid: false,
  verticalVelocity: 0.0,
  smoothingFactor: 1.0
});
assert.ok(descendPitch < -20 && descendPitch >= -35, `Descend pitch should be negative and >= -35, got ${descendPitch}`);

// Smoothing test: with smoothing factor 0.20, pitch should progress smoothly
const smoothedStep1 = calculateDynamicPitch({
  frontHeight: 65.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 0.0,
  isAirborne: false,
  inLiquid: false,
  verticalVelocity: 0.0,
  smoothingFactor: 0.20
});
assert.ok(smoothedStep1 > 0 && smoothedStep1 < climbPitch, `Step 1 should be smoothed between 0 and ${climbPitch}, got ${smoothedStep1}`);

// 3. Amphibious Flotation: Liquid pitch returns to 0
const liquidPitch = calculateDynamicPitch({
  frontHeight: 65.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 20.0,
  isAirborne: false,
  inLiquid: true,
  verticalVelocity: 0.0,
  smoothingFactor: 1.0
});
assert.equal(liquidPitch, 0, "Liquid flotation pitch must level to 0");

// 4. Airborne trajectory alignment
const airborneAscent = calculateDynamicPitch({
  frontHeight: 64.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 0.0,
  isAirborne: true,
  inLiquid: false,
  verticalVelocity: 0.5,
  smoothingFactor: 1.0
});
assert.ok(airborneAscent > 5, "Airborne ascent must pitch slightly nose-up");

const airborneDescent = calculateDynamicPitch({
  frontHeight: 64.0,
  rearHeight: 64.0,
  wheelbase,
  currentPitch: 10.0,
  isAirborne: true,
  inLiquid: false,
  verticalVelocity: -0.6,
  smoothingFactor: 1.0
});
assert.ok(airborneDescent < 0, "Airborne descent must nose down");

// 5. Coordinated Four-Wheel Steering
// Turning left (deltaYaw > 0)
const steerLeft = calculateSteerAngle({
  deltaYaw: 5.0,
  currentSteer: 0.0,
  hasDriver: true,
  steerSpeed: 1.0 // instant response
});
assert.ok(steerLeft > 0 && steerLeft <= 26, `Steer left should be positive, got ${steerLeft}`);

// Maximum steering clamp
const steerMax = calculateSteerAngle({
  deltaYaw: 30.0,
  currentSteer: 0.0,
  hasDriver: true,
  steerSpeed: 1.0
});
assert.equal(steerMax, 26, `Steering angle must clamp to 26, got ${steerMax}`);

// Centering spring when driving straight
const straightCentering = calculateSteerAngle({
  deltaYaw: 0.0,
  currentSteer: 20.0,
  hasDriver: true,
  returnSpeed: 0.35
});
assert.ok(straightCentering < 20.0 && straightCentering > 0.0, "Steering should return toward 0");

// Rear counter-steering ratio
assert.equal(calculateRearSteerAngle(26), -18);
assert.equal(calculateRearSteerAngle(-26), 18);
assert.equal(calculateRearSteerAngle(0), 0);
'''
    res = subprocess.run([node_exe, "--input-type=module", "-e", script],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
