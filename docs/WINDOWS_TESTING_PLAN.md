# Windows automated testing plan

## Agreed scope

- Provide one command on the local Windows PC for automated pack checks and a verified in-game smoke test.
- Automatically prepare the Python environment, create and configure a dedicated world, enable content logging, and load that world; runs require an unlocked Windows desktop.
- Keep visual, audio, and driving review explicit in the proving-ground checklist.
- Use a separate test-only Script API pack for positive runtime assertions; the distributed add-on remains data-only.
- Create a reusable personal skill with executable, editable code that can be adapted for other Minecraft add-ons.
- Scaffold editable runner code into each add-on repository. Each repository owns its copy and runs independently of Codex; later skill changes are applied to existing projects only deliberately.

## Agreed execution contract

Run static checks and packaging, deploy to the dedicated test environment, launch the configured local world, and require a fresh run-specific success marker from the test harness plus fresh content-log checks. Missing evidence, runtime errors, and timeouts produce a nonzero exit code. Preserve a machine-readable report and game-window screenshot when available. A successful spawn does not establish visual, audio, or driving correctness.

The default All command handles the missing-world case automatically. Bootstrap verifies a pinned MIT-licensed Mojang flat-world starter, patches only the new copy to Creative/Peaceful with commands enabled and experiments/multiplayer disabled, attaches the test packs, and enables the content-log setting with an original-file backup. Existing configured worlds remain intact and are reused. Setup prepares the environment and invokes Bootstrap without claiming test success.

A licensed, initialized Minecraft client and unlocked desktop remain necessary. Account or first-launch dialogs can block execution. Acceptance requires the actual live report; automatic world creation and offline tests alone do not establish a game pass.

See [Windows testing](WINDOWS_TESTING.md) for implemented setup, commands, customization, and result interpretation.

The replaced in-game runner allowed missing logs to pass and did not load a world. The new runner requires a fresh matching runtime result and clean logs; screenshots remain diagnostic evidence.
