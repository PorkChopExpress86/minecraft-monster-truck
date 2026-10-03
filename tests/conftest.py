import os
import shutil

import pytest


def pytest_configure(config):
    # Node-backed contract tests skip on machines without node; CI and the pre-commit hook set
    # REQUIRE_NODE=1 so a missing node fails the run instead of silently skipping coverage.
    if os.environ.get("REQUIRE_NODE") == "1" and not shutil.which("node"):
        raise pytest.UsageError("REQUIRE_NODE=1 but node is not on PATH")
