## Agent skills

### Issue tracker

GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (`CONTEXT.md` and `docs/adr/` at repo root). See `docs/agents/domain.md`.

### Game installation and version rev

After finishing changes to `behavior_packs/`, `resource_packs/`, or `scripts/`, offer to rev the version and install with `python scripts/install_addon.py`. A local install (no `--servers`) is already approved when the user's approved plan includes testing in game; otherwise ask first. Always ask before `--servers`: it restarts the user's Docker servers and disconnects players (add `--yes` once they agree).

### Testing

Before treating a passing Scenario Run as proof that a player-reported bug is fixed, read the blind spots in `docs/LINUX_TESTING.md`.
