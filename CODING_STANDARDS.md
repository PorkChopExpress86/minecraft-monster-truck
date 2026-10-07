# Coding standards

Judgement calls a reviewer applies to every diff. Mechanical checks (script syntax, Script API types, unit and contract tests) run in `.githooks/pre-commit` and `.github/workflows/static.yml`; this file covers what they cannot.

## Tests assert behavior, not source text

Test add-on logic through exported pure functions in node-backed tests (`tests/test_driving.py` drives `driving.js` this way), and gameplay outcomes through Scenario Runs. A substring check against production source fits one case only: a forbidden token whose absence is the contract, such as no `gametest` dependency in the production manifest or no `requestDriverJump` after ADR-0017. Flag new assertions such as `"..." in main` or `content.index(...)` that pin how code is written: they break on refactors that keep behavior, and they pass on regressions that keep the text.

## Spec outcomes are hard-coded; tuning is imported

Tests hard-code spec-defining outcomes: what `CONTEXT.md` terms and the ADRs promise (a parked truck does not spin; a drop of 3+ blocks Crush Stomps). Tuning values come from the module that owns them (`DRIVING` in `driving.js`, `LIQUID_DRAG_RETENTION` in `amphibious.js`) rather than being retyped. A changed test expectation names, in its commit, the spec change or ADR it follows.

## Narrow try blocks around engine calls

Production scripts wrap Script API calls in `try`/`catch` so one bad entity cannot stop the tick loop. Keep each `try` around one engine call or one tightly related group, so a failure drops only that work: the handbrake read has its own `try`, separate from the movement read. Flag a `try` that spans independent pieces of work.

## A check that passes on nothing happening carries a positive control

A check whose pass is an absence (the rider stays seated, nothing takes damage, the truck does not move) also passes when its input never landed. In the same check, show that input landing: change one condition so the same input must produce the outcome, as `sneak_stays_seated_over_lava` puts dry land in reach and requires the same Sneak to get the player out. A one-off run with the add-on's behaviour disabled shows the check can fail; it does not cover a later run whose input was lost.

## Tests don't fake what the engine decides

A test proves only what its world models. A scenario that writes state the engine sets from player input (`isSneaking`, rider lists, button state), or a node test whose fake world allows what the engine may not (a player standing on an entity, a key that dismounts), proves only the add-on's reaction. Its row in `docs/ACCEPTANCE_COVERAGE.md` names the Client Input Run check that proves the engine side, or says it has none. Both slipped through before: `two_seat_drop` set `isSneaking`, which the real client never reports on a rider, and a node test asserted a rider set down on the truck's roof, which does not hold a player in the client.

## Driver input enters through `driverInput`

Read driver keys and buttons only through `driverInput` in `main.js`. Scenario Runs supply a Simulated Driver's input through that seam (ADR-0016); input read anywhere else is invisible to them.

## Engine-derived numbers cite their measurement

A constant that encodes engine behavior (drag retention, collision or timing thresholds) points to its evidence: `docs/agents/bedrock-physics.md` or a Scenario Run id.
