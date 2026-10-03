# Coding standards

Judgement calls a reviewer applies to every diff. Mechanical checks (script syntax, Script API types, unit and contract tests) run in `.githooks/pre-commit` and `.github/workflows/static.yml`; this file covers what they cannot.

## Tests assert behavior, not source text

Test add-on logic through exported pure functions in node-backed tests (`tests/test_driving.py` drives `driving.js` this way), and gameplay outcomes through Scenario Runs. A substring check against production source fits one case only: a forbidden token whose absence is the contract, such as no `gametest` dependency in the production manifest or no `requestDriverJump` after ADR-0017. Flag new assertions such as `"..." in main` or `content.index(...)` that pin how code is written: they break on refactors that keep behavior, and they pass on regressions that keep the text.

## Spec outcomes are hard-coded; tuning is imported

Tests hard-code spec-defining outcomes: what `CONTEXT.md` terms and the ADRs promise (a parked truck does not spin; a drop of 3+ blocks Crush Stomps). Tuning values come from the module that owns them (`DRIVING` in `driving.js`, `LIQUID_DRAG_RETENTION` in `amphibious.js`) rather than being retyped. A changed test expectation names, in its commit, the spec change or ADR it follows.

## Narrow try blocks around engine calls

Production scripts wrap Script API calls in `try`/`catch` so one bad entity cannot stop the tick loop. Keep each `try` around one engine call or one tightly related group, so a failure drops only that work: the handbrake read has its own `try`, separate from the movement read. Flag a `try` that spans independent pieces of work.

## Driver input enters through `driverInput`

Read driver keys and buttons only through `driverInput` in `main.js`. Scenario Runs supply a Simulated Driver's input through that seam (ADR-0016); input read anywhere else is invisible to them.

## Engine-derived numbers cite their measurement

A constant that encodes engine behavior (drag retention, collision or timing thresholds) points to its evidence: `docs/agents/bedrock-physics.md` or a Scenario Run id.
