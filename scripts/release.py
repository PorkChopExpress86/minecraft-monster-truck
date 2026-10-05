"""Release the add-on: rev the patch version, install it, record the install in docs/STATE.md, and commit.

Usage: release.py [--servers creative,survival --yes] [--push] [-m MESSAGE]

The working tree must be clean, so the release commit holds only the version rev and the STATE.md line.
--servers restarts the user's Docker servers (ask first; AGENTS.md). --push pushes the release commit.
"""
import argparse
from datetime import date
from pathlib import Path
import re
import subprocess
import sys

try:
    from scripts.install_addon import REPO_ROOT, SERVER_CONTAINERS, install as install_addon
    from scripts.version_manager import get_repo_version, version_to_str
except ImportError:
    from install_addon import REPO_ROOT, SERVER_CONTAINERS, install as install_addon
    from version_manager import get_repo_version, version_to_str


def run_git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def install_revved(servers=(), assume_yes=False):
    return install_addon(rev=True, servers=servers, assume_yes=assume_yes)


def repo_version(root):
    return version_to_str(get_repo_version(root))


def record_install(state_path, line):
    """Put `line` in place of STATE.md's Installed: line, or first under ## Now when there is none."""
    text = state_path.read_text(encoding="utf-8")
    if re.search(r"(?m)^Installed: .*$", text):
        text = re.sub(r"(?m)^Installed: .*$", lambda _: line, text, count=1)
    else:
        text = text.replace("## Now\n", f"## Now\n{line}\n", 1)
    state_path.write_text(text, encoding="utf-8")


def release(servers=(), assume_yes=False, push=False, message=None, root=REPO_ROOT,
            git=run_git, install=install_revved, version=repo_version, today=lambda: date.today().isoformat()):
    root = Path(root)
    dirty = git(root, "status", "--porcelain").stdout.strip()
    if dirty:
        print("[ERROR] Commit or stash these changes first; a release commit holds only the release:\n" + dirty,
              file=sys.stderr)
        return 2
    code = install(servers=servers, assume_yes=assume_yes)
    if code != 0:
        print("[ERROR] Install failed; the version rev is left uncommitted for review.", file=sys.stderr)
        return code
    revision = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
    ver = version(root)
    targets = "the local client" + (f" and servers {', '.join(servers)}" if servers else "")
    record_install(root / "docs/STATE.md", f"Installed: v{ver} ({revision}) on {targets}, {today()}.")
    commit = git(root, "commit", "-am", message or f"Release {ver}")
    if commit.returncode != 0:
        print(f"[ERROR] git commit failed:\n{commit.stdout}{commit.stderr}", file=sys.stderr)
        return 1
    print(f"[OK] Released v{ver} ({revision}) to {targets}.")
    if push:
        pushed = git(root, "push")
        if pushed.returncode != 0:
            print(f"[ERROR] git push failed:\n{pushed.stderr}", file=sys.stderr)
            return 1
        print("[OK] Pushed.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--servers", default="", help="Also install to Docker servers: " + ",".join(SERVER_CONTAINERS))
    parser.add_argument("--yes", action="store_true", help="Restart --servers containers without asking")
    parser.add_argument("--push", action="store_true", help="Push the release commit")
    parser.add_argument("-m", "--message", help="Release commit message (default: Release <version>)")
    args = parser.parse_args(argv)
    servers = [s.strip() for s in args.servers.split(",") if s.strip()]
    unknown = [s for s in servers if s not in SERVER_CONTAINERS]
    if unknown:
        parser.error(f"unknown server(s): {', '.join(unknown)}")
    return release(servers=servers, assume_yes=args.yes, push=args.push, message=args.message)


if __name__ == "__main__":
    sys.exit(main())
