"""Runs the node behaviour tests in tests/js (node --test) as one pytest test per file."""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JS_TESTS = sorted((REPO_ROOT / "tests" / "js").glob("*.test.mjs"))


@pytest.mark.parametrize("test_file", JS_TESTS, ids=lambda path: path.name)
def test_node_behaviour(test_file):
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("node is not installed")
    res = subprocess.run([node_exe, "--test", "--test-reporter=spec", str(test_file)],
                         cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_js_behaviour_files_are_collected():
    assert JS_TESTS, "tests/js must contain *.test.mjs files"
