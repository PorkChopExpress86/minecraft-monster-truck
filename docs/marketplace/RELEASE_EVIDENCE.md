# Monster Truck release evidence

Checked September 7, 2026, America/Chicago (September 8 UTC).

## Build

- Artifact: `dist/MonsterTruck.mcaddon`
- Size: 21,158 bytes
- SHA-256: `BBFFB7A9235A695000FC87C95FFEDDF498FF1424EA8D84A6DCED6154C7EC1193`
- Command: `powershell.exe -NoProfile -File .\Test-Addon.ps1 -Mode All`
- Run: `417c38379e9c421fb63bd080d67d3e23`
- [Local report](../../dist/bedrock-tests/417c38379e9c421fb63bd080d67d3e23/report.json)

## Observed results

59 pytest tests passed. Repository validation and packaging returned exit code 0.

The runtime harness emitted PASS for six colors, required components and two seats per vehicle; two-block stepping with horizontal impulses; 1,000 health; 75% melee damage reduction; fall damage immunity; stationary contact safety; and a moving truck killing a mob.

The overall run returned exit code 1. Its error was `Showcase requires at least two successful screenshots`; the capture note was `Minecraft screenshot capture exceeded 20 seconds`. There were no captured screenshots in this run. Final logs were collected, and the report listed no content warnings. Do not turn the harness PASS into a claim that the complete workflow passed.

## Visual review

Both existing `docs/images/` images were opened and inspected during preparation. They show all six colors with recognizable truck geometry and no obvious missing-texture pattern. The close-up is the stronger lead image. The other image contains background animals and a narrow dark left border; both use a flat test-world setting. Neither shows actual driving or seated players. These are portfolio candidates, not final Marketplace artwork.

## Outstanding evidence

A Game-only retry (`04d08c90bbde43d0af98241f5a587d17`) reproduced the same screenshot timeout and overall failure, while the runtime assertions again emitted PASS. No cause has been established for the capture failure.

The outer archive and both inner MCPacks were inspected: only the two production packs and their expected assets are included; no test scripts, local configuration, or test world were present. The official `@minecraft/creator-tools` npm package was resolved to version 0.17.8, but its initial `mct --help` invocation did not finish and was interrupted. No official validator results are claimed.

Official Creator Tools validation, a successful fresh screenshot workflow, manual controls/audio/multiplayer acceptance, asset rights confirmation, and any additional target-device testing remain open. The portfolio and submission drafts are not approval or certification claims.
