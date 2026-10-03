#!/usr/bin/env bash
# Linux counterpart of Test-Addon.ps1. See docs/LINUX_TESTING.md.
# Usage: ./test-addon.sh [Setup|Bootstrap|Doctor|Configure|Static|Scenarios|Game|All] [--world DIR --log-directory DIR] [--only scenario,...]
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-All}"
shift || true
python="${PYTHON:-python3}"
test_python="$root/.venv-testing/bin/python"

case "$mode" in
  Setup|Bootstrap|Doctor|Configure|Static|Scenarios|Game|All) ;;
  *) echo "Unknown mode '$mode'. Use Setup, Bootstrap, Doctor, Configure, Static, Scenarios, Game, or All." >&2; exit 2 ;;
esac

if [[ "$mode" =~ ^(Setup|Bootstrap|All|Game)$ || ! -x "$test_python" ]]; then
  [[ -x "$test_python" ]] || "$python" -m venv "$root/.venv-testing"
  "$test_python" -m pip install -q -r "$root/requirements-testing.txt"
  [[ "$mode" == Setup ]] && mode=Bootstrap
fi

if [[ "$mode" =~ ^(Bootstrap|Static|All)$ ]]; then
  # Dev tooling for the Script API type check, and the pre-commit guardrail.
  [[ -d "$root/node_modules" ]] || (cd "$root" && npm ci --silent)
  git -C "$root" config core.hooksPath .githooks
fi

if [[ "$mode" =~ ^(Static|All)$ ]]; then
  "$root/node_modules/.bin/tsc" -p "$root/jsconfig.json"
fi

exec "$test_python" "$root/scripts/bedrock_test.py" "${mode,,}" "$@"
