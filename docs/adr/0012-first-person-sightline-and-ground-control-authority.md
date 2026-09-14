# First-Person Cab Sightline Clearance and Ground Control Authority

We decided to:
1. Re-enable `minecraft:input_ground_controlled: {}` on `blake:monster_truck` alongside `minecraft:can_power_jump: {}`, `minecraft:horse.jump_strength: { "value": 0.85 }`, `minecraft:is_tamed: {}`, and `minecraft:is_saddled: {}`. This restores native responsive WASD keyboard steering, forward acceleration, and reverse authority to the driver seat.
2. Correct the seat coordinates in `minecraft:rideable` to `[0.45, 1.15, 0.15]` for Seat 0 (Driver Seat, front-left door) and `[-0.45, 1.15, 0.15]` for Seat 1 (Passenger Seat, front-right door). Approaching the vehicle's left-hand driver door now reliably boards the player into controlling Seat 0.
3. Lower the seated elevation to $Y = 1.15$ blocks ($18.4$ model units) and elevate the cab roof to $Y = 46\text{--}48$ with a $12$-unit transparent windshield ($Y = 34\text{--}46$). This eliminates roof clipping in first-person view, placing the rider's eye line ($Y \approx 40.8$) cleanly inside the windshield aperture with $>5$ units of vertical headroom.
4. Provide automated test verification spanning both static mathematical raycasting (`tests/test_cab_sightlines.py`) and live Bedrock harness assertions (`testing/harness/assertions.js`).
