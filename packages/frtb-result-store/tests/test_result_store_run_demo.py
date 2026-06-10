from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_result_store_run_demo_smoke() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    demo = repo_root / "packages" / "frtb-result-store" / "examples" / "run_demo.py"

    completed = subprocess.run(
        [sys.executable, str(demo)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Result-store demo complete" in completed.stdout
    assert "total capital: 142.00 USD" in completed.stdout
    assert "attribution records: 3" in completed.stdout
    assert "lineage source: snapshot-demo-suite-001" in completed.stdout
