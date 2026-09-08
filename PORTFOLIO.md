# Monster Truck

A Minecraft Bedrock vehicle project built around a simple idea: craft a truck, choose your color, and bring a passenger on your next adventure.

![Monster Truck in six paint colors, with a red truck in the foreground](docs/images/monster-truck-closeup.png)

**Status:** playable development build. **Platform tested:** Minecraft Bedrock for Windows. **Planned release:** free. **Marketplace status:** not published.

## The experience

Monster Truck adds a lifted pickup with oversized tires, exposed axles and suspension, an open cargo bed, and separate Driver and Passenger Seats. Six paint colors let players personalize their vehicle: red, blue, green, yellow, black, and white.

The vehicle is designed for Survival crafting and exploration, with a Creative spawn egg for quick experimentation. Controlled Auto-Step supports two-block stepped terrain. Engine audio and wheel animation complete the intended driving experience.

![Rear three-quarter view showing the six colors, cargo beds, suspension, and tires](docs/images/monster-truck-colors.png)

## What this project demonstrates

- **Vehicle design:** a recognizable pickup silhouette with chunky tread, high ground clearance, color-matched hubs, and visible undercarriage detail.
- **Bedrock gameplay integration:** rideable entity configuration, Survival crafting, repainting interactions, durability, and movement-dependent contact damage.
- **Asset production:** repository-owned geometry and texture generators, plus a synthesizer for engine sound effects.
- **Testing discipline:** static checks and a separate test-world harness for runtime behavior. The playable add-on remains data-driven; test scripts are excluded from its behavior pack.

The images above are captured in Minecraft. They show the current visual design rather than a concept render.

## Evidence and current limitations

On September 7, 2026 (local time), the project passed **59 automated tests**, its repository validator, and add-on packaging. A fresh live run reported passing checks for all six vehicle color states, both configured seats, two-block stepping under horizontal impulses, durability, and moving-versus-stationary contact damage. The overall run failed because screenshot capture timed out; this is not recorded as a complete live-test pass.

Actual keyboard driving, dye clicks, two-player riding, audible sound playback, and controller/touch usability still need recorded acceptance checks. Current evidence does not establish console/mobile compatibility or Marketplace certification. See [release evidence](docs/marketplace/RELEASE_EVIDENCE.md) for the exact build and run details.

## Explore the project

- [Player guide, controls, and installation](README.md)
- [Survival recipe](docs/RECIPE_GUIDE.md)
- [Manual gameplay acceptance checklist](docs/PROVING_GROUND.md)
- [Automated testing workflow](docs/WINDOWS_TESTING.md)
- [Local packaged build](dist/MonsterTruck.mcaddon) — build locally using the player guide; this ignored build path will not become a public download just by publishing this page.

## Next showcase milestone

Record a short gameplay video showing real driving, repainting, Survival crafting, and a passenger. Build a small proving-ground scene to show the truck in use, then publish a versioned free download with tested-device notes and a feedback channel. Final creator credits and asset ownership confirmations are still pending.

This is the first portfolio project. Future entries should demonstrate distinct completed experiences and real player feedback; no unreleased concepts are presented here as shipped work.
