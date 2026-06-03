# CI job matrix (from `classify_changed_paths`)

Run in Step 0.5 after recording the PR. Outputs drive which jobs **must** pass on
the PR (others may be skipped).

```bash
python3 scripts/ci/classify_changed_paths.py
# or capture flags:
eval "$(python3 scripts/ci/classify_changed_paths.py | sed 's/^/export changes_/')"
```

## Flag → required jobs

| `changes_*` flag | When true | PR jobs that must pass |
| --- | --- | --- |
| *(always)* | Every PR | `quality-control`, `version-bump-guard`, `uv-lock-guard`, `ci-required` |
| `code` | Package/runtime code, Makefile, lockfile, agent instruction paths under `.grok/` etc. | `lint`, `typecheck`, `build`, `test (3.11)` |
| `docs` | `*.md`, `docs/`, PR template, agent instruction paths | `docs` |
| `dependency` | `pyproject.toml`, `uv.lock`, dependabot | `dependency-audit`, `sbom` |
| `notebooks` | `frtb-ima` notebooks/fixtures/src paths (see script) | `notebooks` |
| `examples` | `frtb-ima` examples paths (see script) | `examples` |
| `workflow` | `.github/workflows/`, `scripts/ci/` | All of the above (full matrix) |

`workflow` or non-PR `full` forces the broadest job set.

## Skipped on PRs (not failures)

| Job | Reason |
| --- | --- |
| `test (3.12)`, `test (3.13)` | `test-compat` — schedule/dispatch only |

## Docs-only fast path

When `changes_code=false` and `changes_docs=true` (and no `workflow` forcing full):

- Phase 1 still required (`quality-control`, `docs`, guards).
- Skip Phases 2–3 unless the user did not pass `--skip-reviews` and human review is requested.
- Local validation: `make agent-guard` + `make docs-check` (not full `ci-local`).

## Narrow local validation (by class)

| Change class | After a fix, prefer |
| --- | --- |
| Docs / agent skills only | `make docs-check` |
| Single package code | `uv run pytest packages/<pkg>/tests` + `make quality-control` |
| Cross-cutting / maturity / drift | `make quality-control` |
| Pre-push default | `make agent-guard` then narrowest row above |

See `references/qc-failures.md` when `quality-control` fails.