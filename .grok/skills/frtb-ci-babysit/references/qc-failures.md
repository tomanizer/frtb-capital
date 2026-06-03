# quality-control failure playbook

When `quality-control` or `make quality-control` fails locally:

## Download CI artifacts

```bash
RUN_ID=$(gh pr view $PR --json statusCheckRollup --jq '
  [.statusCheckRollup[] | select(.name=="quality-control") | .detailsUrl]
  | first' | sed -n 's|.*/actions/runs/\([0-9]*\).*|\1|p')
gh run download "$RUN_ID" -n package-maturity -D /tmp/qc-$PR/maturity 2>/dev/null || true
gh run download "$RUN_ID" -n code-drift -D /tmp/qc-$PR/drift 2>/dev/null || true
```

## By failure type

| Symptom | Action |
| --- | --- |
| `maturity-check` / package registry | Read `dist/quality/package-maturity.json`; update `docs/quality/package_maturity.toml` and evidence paths. |
| `drift-check` / code drift | `make drift-report`; intentional baseline growth → `make drift-baseline` with explicit diff in PR. |
| `docs-staleness` | Fix paths listed in log or run `.grok/skills/frtb-doc-audit/SKILL.md`. |
| `import-lint` / kernel boundary | Remove sibling imports; never noqa without ADR. |
| `import-smoke` | Fix broken public imports or `PACKAGE_METADATA` entrypoints. |
| `simplification-drift` | Address rubric findings or document exception in PR. |

Re-run the narrowest local target after each fix:

- Docs only: `make docs-check`
- Code: `make quality-control` or failing sub-target from Makefile