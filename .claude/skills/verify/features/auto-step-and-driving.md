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
- **Steering verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only steering`. The scenario asserts that A turns a parked truck's wheels fully left (steer angle -26) without the truck spinning, the wheels re-center on release, turning the Simulated Driver's body does not steer, and while rolling A turns the truck at least 30 degrees left and D at least 30 degrees right, each moving it at least 2 blocks sideways. It does not compare turning radius at low and high speed.
- **Incline pitch verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only incline_pitch`. The scenario asserts that chassis pitch smoothly tracks hill climbs and drops.
- **Real client throttle drive.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only w_drives -Trace`. The runner injects physical W keystrokes into the real game window for 1.5 s, asserting at least 3 blocks of forward travel and at most 1 block sideways.
- **Real client reverse drive.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only s_brakes_and_reverses -Trace`. The runner injects physical S keystrokes, asserting deceleration followed by straight rearward displacement.
- **Door-side dismount.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only door_dismount`. With both seats taken, the scenario sets the driver and then, in a fresh truck, the passenger down 1.5 to 2.2 blocks out of their own seat's door (the truck's left for the driver, its right for the passenger), on a solid block with two blocks of air above. Its Sneak is faked; `-Mode Client -Only sneak_dismounts` checks that a real Sneak sets the driver down outside the driver's door.
- **Real client steering.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only a_turns_left,d_turns_right -Trace`. The runner asserts that A produces negative yaw deflection and D produces positive yaw deflection.

## Gotchas

- Mouse look direction does not steer the monster truck; steering is governed strictly by A and D keys.
- Auto-step requires forward driving input (W); a stationary truck pushed into a ledge does not climb.
- Vertical obstacles of 3 or more blocks cannot be climbed and will halt forward progress.
- Client Input Runs take over keyboard focus; touching the mouse or keyboard during a Client run aborts execution via the focus guard.
