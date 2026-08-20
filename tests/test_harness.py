from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_harness_check_passes() -> None:
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/check_harness.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "HARNESS_CHECK_OK"
