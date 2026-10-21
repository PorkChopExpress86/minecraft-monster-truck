"""Find a test run's report folder in every checkout of this repository.

Usage: find_run.py RUN_ID_PREFIX

Each git worktree writes runs to its own dist/bedrock-tests/<run id>/, so a run started elsewhere is not under
this checkout's dist. Prints one line per match: folder, mode, status, start time. Exits 1 when none match.
"""
import argparse
import glob
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def checkouts(root):
    listing = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, check=True).stdout
    return [Path(line.removeprefix("worktree ")) for line in listing.splitlines() if line.startswith("worktree ")]


def find_runs(prefix, roots):
    for checkout in roots:
        for run in sorted((checkout / "dist/bedrock-tests").glob(glob.escape(prefix) + "*")):
            report = run / "report.json"
            yield run, json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("prefix", help="the start of a run id, as a report or task brief names it")
    prefix = parser.parse_args(argv).prefix
    if not prefix or "/" in prefix or "\\" in prefix:
        parser.error("give the start of a run id")
    found = False
    for run, report in find_runs(prefix, checkouts(ROOT)):
        found = True
        print(run, report.get("mode", "-"), report.get("status", "-"), report.get("started_utc", "-"))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
