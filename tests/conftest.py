import os
import shutil

import pytest


def pytest_configure(config):
    # Node-backed contract tests skip on machines without node; CI and the pre-commit hook set
    # REQUIRE_NODE=1 so a missing node fails the run instead of silently skipping coverage.
    if os.environ.get("REQUIRE_NODE") == "1" and not shutil.which("node"):
        raise pytest.UsageError("REQUIRE_NODE=1 but node is not on PATH")


@pytest.fixture(autouse=True)
def isolate_git(monkeypatch):
    """Drop the GIT_* variables a git hook exports. Under `git commit -a` the pre-commit hook sets an absolute
    GIT_INDEX_FILE; inherited, it sends a fixture repo's `git add` into the commit being made."""
    for name in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(name)
