# Controlled Auto-Step and Ground Driving

Ground driving lets a seated player pilot the monster truck (`blake:monster_truck`) across rugged overland terrain with responsive W/S throttle and A/D coordinated four-wheel steering while the mouse only controls the view. The vehicle effortlessly climbs vertical 2-block stepped terrain obstacles without requiring jump inputs, while preserving cab interior sightlines and terrain-conforming pitch.

## Sub-features

- `drive-throttle`: W accelerates forward up to cruising top speed (1.1 blocks/tick); S brakes to a stop and reverses straight back.
- `drive-steer`: A turns front wheels left and rear wheels right; D turns front wheels right and rear wheels left; vehicle turns only while rolling.
- `drive-auto-step`: Automatically ascends vertical 2-block ledges while driven forward without manual jump inputs.
- `drive-sightline`: Driver eye-line is positioned level with the clear windshield, providing an unobstructed forward sightline over the sloped hood.
- `drive-incline-pitch`: Dual-axle chassis and wheels smoothly pitch to match uphill climbs and downhill slopes.
- `drive-door-dismount`: Sneak dismount on solid ground safely teleports the driver 1.8 blocks out beside the left driver door (or passenger out beside the right passenger door) with 2 blocks vertical air clearance.
- `visual-engine-suspension`: Exposed V8 engine block, supercharger blower scoop, side exhaust headers, cab roll cage, and 4-link dual-reservoir coilover suspension.

## How to get to it (user POV)

- Approach the monster truck and interact with it (right-click / tap) without sneaking to enter the Driver Seat.
- Press `W` to accelerate forward; press `S` to brake and reverse.
- Press `A` to steer left; press `D` to steer right.
- Steer forward into a 1- or 2-block vertical cliff or ledge to auto-step upward.
- Look around with mouse / joystick while driving without altering the vehicle's turning direction.
- Press Sneak (`Shift` / `K`) while on solid ground to dismount out to the side of the driver door.


## Driving it with Test-Addon.ps1

Preconditions:

- Docker Desktop is active with Bedrock Dedicated Server image available.
- For physical keystroke tests, Minecraft Bedrock client is installed and closed, and the desktop is unlocked.

- **Auto-step verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only auto_step`. The scenario asserts that a driven truck ascends a 2-block vertical ledge (reaching height +2.00) without player jump input, and that a 3-block wall stops the vehicle.
- **Steering verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only steering`. The scenario asserts that A deflects the wheels left, D deflects them right, turning occurs only while rolling, and the turning radius at low speed is tighter than at high speed.
- **Incline pitch verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only incline_pitch`. The scenario asserts that chassis pitch smoothly tracks hill climbs and drops.
- **Real client throttle drive.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only w_drives -Trace`. The runner injects physical W keystrokes into the real game window, asserting forward travel exceeding 20 blocks.
- **Real client reverse drive.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only s_brakes_and_reverses -Trace`. The runner injects physical S keystrokes, asserting deceleration followed by straight rearward displacement.
- **Real client steering.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only a_turns_left,d_turns_right -Trace`. The runner asserts that A produces negative yaw deflection and D produces positive yaw deflection.

## Gotchas

- Mouse look direction does not steer the monster truck; steering is governed strictly by A and D keys.
- Auto-step requires forward driving input (W); a stationary truck pushed into a ledge does not climb.
- Vertical obstacles of 3 or more blocks cannot be climbed and will halt forward progress.
- Client Input Runs take over keyboard focus; touching the mouse or keyboard during a Client run aborts execution via the focus guard.
