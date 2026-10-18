# Handbrake Drift and High-Drop Suspension

Holding Space engages the rear-wheel handbrake, bringing the truck to a rapid straight-line stop or initiating a wide-angle power drift when steering into turns at high speed, regaining grip upon release without ever dismounting the driver. Massive tires and heavy-duty pneumatic shock absorption provide complete fall damage immunity for both the truck and its seated riders from extreme drops, while landings from heights of 3 or more blocks trigger a destructive Crush Stomp that damages hostiles beneath while sparing riders, allies, and vehicles.

## Sub-features

- `handbrake-stop`: Holding Space locks the rear wheels, stopping a forward-moving truck within 30 ticks without turning, and preventing a parked truck from rolling.
- `handbrake-drift`: Holding Space while steering at speed swings the rear wheels out into a lateral slide (slip >= 10 degrees); releasing Space restores normal grip (slip <= 3 degrees) within 12 ticks.
- `handbrake-retention`: Holding Space never dismounts the driver or passenger (Jump input permission is disabled for seated riders while reading button state).
- `suspension-immunity`: Vehicle and seated riders take 100% zero fall damage from any fall height upon landing.
- `crush-stomp`: Landing from a drop of 3 or more blocks inflicts heavy kinetic impact and radial knockback on hostile mobs beneath, while completely sparing seated players, nearby riders, and tamed companions.

## How to get to it (user POV)

- While driving forward at speed, hold `Space` to perform a hard brake.
- While cornering with `A` or `D` at speed, hold `Space` to break rear traction and drift sideways; release `Space` to snap back to linear grip.
- Drive off high cliffs, ramps, or ledges: the truck lands smoothly with venting pneumatic audio and wheel impact dust without injuring vehicle or passengers.
- Drop down onto hostile mobs from 3 or more blocks above to crush them on touchdown.

## Driving it with Test-Addon.ps1

Preconditions:

- Docker Desktop is active with Bedrock Dedicated Server image.
- Dedicated Test World is configured.

- **Handbrake drift verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only handbrake`. The scenario asserts that held Space stops straight travel within 30 ticks, holds parked position against W throttle, produces slip >= 10 degrees during steering, recovers grip <= 3 degrees within 12 ticks of release, and maintains rider retention throughout.
- **Pneumatic shock absorption.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only shock_absorption`. The scenario drops the truck 16 blocks, asserting 1000/1000 health on the truck, 20/20 health on the seated driver, and continuous seat attachment.
- **Two-seat drop verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only two_seat_drop`. The scenario drops a fully loaded truck 8 blocks, asserting driver and passenger remain at 20/20 health and seated. Inside the landing window a passenger who leaves is put back in seat 1 and fall damage to both riders is cancelled; after the window the same exit lets them go and fall damage lands, and later on-foot falls hurt both.
- **Crush Stomp verification.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Scenarios -Only crush_stomp`. The scenario asserts that a 4-block drop inflicts >= 60 contact damage on a zombie beneath while inflicting 0 damage on the driver, adjacent players, tamed wolves, and parked trucks, and that drops under 3 blocks trigger no crush impact.
- **Client Space retention.** Run `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode Client -Only space_keeps_rider -Trace`. The runner asserts that with physical W and Space held simultaneously, the player remains in the Driver Seat across all sampled ticks with near-zero creep.

## Gotchas

- In vanilla Minecraft Bedrock, Space normally dismounts vehicles; the add-on overrides this by toggling Jump input permission off while seated.
- Crush Stomp requires a genuine airborne drop of at least 3 blocks; driving over a small 1- or 2-block ledge does not trigger Crush Stomp.
- Sneak cannot get a rider out mid-air: through a drop and for 8 ticks after landing the add-on puts a rider who leaves back in the seat, still protected (`-Mode Client -Only sneak_during_drop`). After that window Sneak gets them out and fall protection ends with the exit.
