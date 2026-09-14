## Agent skills

### Issue tracker

GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (`CONTEXT.md` and `docs/adr/` at repo root). See `docs/agents/domain.md`.

### Game Installation & Version Rev Prompt

Whenever you complete work, bug fixes, or changes to the add-on files (`behavior_packs/`, `resource_packs/`, or `scripts/`), you MUST proactively prompt the user asking whether they would like to rev the version and install the updated add-on directly to the Minecraft Bedrock game installed on their computer (running `python scripts/install_addon.py` upon confirmation). The installation script will rev the version, deploy to global development packs and active worlds, synchronize world pack manifests, and verify that the installed game version matches the finished repository version.
