---
name: open-items
description: Report what is still open in this project, with every docs/STATE.md note re-checked against the repo. Use when the user asks what's open, left, pending or next.
---

STATE.md notes go stale silently; report only what you re-check this turn.

1. Run `gh issue list --state open --json number,title` and `gh run list --branch main --limit 4 --json name,status,conclusion,headSha`.
2. Read `docs/STATE.md` `## Open items` and `## Next`.
3. Re-check every Open items line against its evidence: grep the quoted text, symbol or `file:line` it names, or read the issue it cites. Done when each line is marked **holds** or **stale** with the command that showed it.
4. Delete stale lines from `## Open items` (a finished one moves to `## Done` with its result), and commit the change locally.
5. Report, in this order: open issues grouped into in-game checks for the user and code-side work, then the open items that hold, then CI per commit. Name any stale line you removed. Put the full issue URL on every issue number.
