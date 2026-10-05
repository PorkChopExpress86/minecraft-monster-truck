"""scripts/release.py: rev, install, record the installed version in docs/STATE.md, commit, push on request."""
import subprocess

from scripts import release

STATE = "## Goal\nx\n## Now\nworking on y\n## Next\n1. z\n"


class Git:
    def __init__(self, dirty=""):
        self.calls = []
        self.dirty = dirty

    def __call__(self, root, *args):
        self.calls.append(args)
        out = {"status": self.dirty, "rev-parse": "abc1234\n"}.get(args[0], "")
        return subprocess.CompletedProcess(args, 0, out, "")


def run(tmp_path, git, installed=0, **kwargs):
    (tmp_path / "docs").mkdir(exist_ok=True)
    state = tmp_path / "docs/STATE.md"
    if not state.exists():
        state.write_text(STATE)
    installs = []

    def install(**options):
        installs.append(options)
        return installed

    code = release.release(root=tmp_path, git=git, install=install, version=lambda root: "1.0.14",
                           today=lambda: "2026-10-05", **kwargs)
    return code, installs, state.read_text()


def test_a_dirty_tree_is_refused_before_anything_is_installed(tmp_path):
    git = Git(dirty=" M behavior_packs/x.js\n")
    code, installs, state = run(tmp_path, git)
    assert code == 2 and installs == [] and state == STATE
    assert [c for c in git.calls if c[0] == "commit"] == []


def test_a_failed_install_commits_nothing(tmp_path):
    git = Git()
    code, _, state = run(tmp_path, git, installed=1)
    assert code == 1 and state == STATE
    assert [c for c in git.calls if c[0] == "commit"] == []


def test_a_release_records_the_install_in_state_and_commits_without_pushing(tmp_path):
    git = Git()
    code, installs, state = run(tmp_path, git, servers=["creative", "survival"], assume_yes=True)
    assert code == 0
    assert installs == [{"servers": ["creative", "survival"], "assume_yes": True}]
    assert "## Now\nInstalled: v1.0.14 (abc1234) on the local client and servers creative, survival, 2026-10-05.\n" \
        "working on y\n" in state
    assert ("commit", "-am", "Release 1.0.14") in git.calls
    assert [c for c in git.calls if c[0] == "push"] == []


def test_a_second_release_replaces_the_installed_line(tmp_path):
    run(tmp_path, Git())
    code, _, state = run(tmp_path, Git(), message="Release 1.0.14 with a fix")
    assert code == 0 and state.count("Installed: ") == 1
    assert "Installed: v1.0.14 (abc1234) on the local client, 2026-10-05." in state


def test_push_only_when_asked(tmp_path):
    git = Git()
    assert run(tmp_path, git, push=True)[0] == 0
    assert git.calls[-1] == ("push",)
