"""Capture GitHub repository-control settings for audit evidence.

The script shells out to the GitHub CLI so it can reuse the operator's existing
authentication and repository permissions. It records only repository settings;
it does not modify branch protection.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Repository in OWNER/NAME form.")
    parser.add_argument("--branch", default="main", help="Protected branch to inspect.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/repo-controls"),
        help="Directory for captured JSON evidence.",
    )
    args = parser.parse_args()

    owner, repo_name = _split_repo(args.repo)
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "frtb_capital_repo_controls_snapshot_v1",
        "captured_at": datetime.now(UTC).isoformat(),
        "repository": args.repo,
        "branch": args.branch,
        "pagination": {
            "rulesets": True,
        },
        "endpoints": {
            "repository": _gh_api(f"repos/{owner}/{repo_name}"),
            "branch_protection": _gh_api(
                f"repos/{owner}/{repo_name}/branches/{args.branch}/protection"
            ),
            "rulesets": _gh_api(f"repos/{owner}/{repo_name}/rulesets", paginate=True),
        },
    }
    target = args.output / f"{repo_name}-{args.branch}-repo-controls.json"
    target.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


def _split_repo(value: str) -> tuple[str, str]:
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2 or not all(parts):
        raise ValueError("--repo must use OWNER/NAME form")
    return parts[0], parts[1]


def _gh_api(endpoint: str, *, paginate: bool = False) -> Any:
    command = ["gh", "api"]
    if paginate:
        command.extend(("--paginate", "--slurp"))
    command.append(endpoint)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "command": command,
            "error": "gh CLI not found in PATH",
        }
    if result.returncode != 0:
        return {
            "available": False,
            "command": command,
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
            "stdout": result.stdout.strip(),
        }
    return json.loads(result.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
