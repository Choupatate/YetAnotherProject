"""Runs the plain-Node unit tests for the /tree view-scope logic
(app/static/js/tree-logic.js), the shared localStorage wrapper
(app/static/js/safe-storage.js), and the shared fetch/JSON response
helper (app/static/js/fetch-json.js) as part of the bare `pytest` run.
Skipped, not failed, when node isn't on PATH — the app has no Node
dependency and never should; this just piggybacks on it being present
in CI."""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node not available on PATH")
def test_tree_logic_pure_functions():
    result = subprocess.run(
        [NODE, "tests/js/tree_logic_test.mjs"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(NODE is None, reason="node not available on PATH")
def test_safe_storage_wrapper():
    result = subprocess.run(
        [NODE, "tests/js/safe_storage_test.mjs"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(NODE is None, reason="node not available on PATH")
def test_fetch_json_wrapper():
    result = subprocess.run(
        [NODE, "tests/js/fetch_json_test.mjs"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
