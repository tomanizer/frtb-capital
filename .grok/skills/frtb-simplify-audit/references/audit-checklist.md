# Simplification audit checklist

Use during Step 3 of `frtb-simplify-audit`. Mark pass / finding per package.

## Mechanical gates

- [ ] `make agent-ensure AGENT=<agent> TASK=simplify-audit` passed (and `cd` done if printed)
- [ ] `uv run python scripts/ci/check_simplification_drift.py` — no unexpected findings (or each suppressed with `# simplify-audit: keep - <reason>`)
- [ ] No sibling capital imports in `packages/*/src` (orchestration excepted per policy)

## Size thresholds

| Signal | Threshold | Typical priority |
| --- | --- | --- |
| Source file LOC | > 1000 | P1 |
| Source file LOC | > 500 | P2 |
| Function LOC | > 120 | P1 |
| Nesting depth | ≥ 5 | P1 |
| Repeated trivial `return fn(...)` wrappers | ≥ 3 same pattern | P1 |

```bash
find packages/<pkg>/src -name '*.py' -print | xargs wc -l | sort -nr | head -15
```

## Duplication patterns (rg)

```bash
rg "_hash_payload|stable_json_hash" packages/<pkg>/src -n
rg "_require_text|_merge_citation|_slug" packages/<pkg>/src -n
rg "def build_.*_from_sensitivities" packages/<pkg>/src -n
rg "accepted_row_dataclasses_materialized" packages/<pkg>/src packages/<pkg>/tests -n
```

## Row vs batch

- [ ] Document whether row and batch paths duplicate validation/classification/capital
- [ ] Hash payloads aligned between audit and batch modules
- [ ] Regression tests identified before any merge

## Wrappers and style

- [ ] List pass-through public functions (single `return` of one call)
- [ ] Flag “template” docstrings repeated with only risk-class names changed
- [ ] Note placeholder modules (`attribution`, `impact`, `scaffold`) — must stay explicitly unsupported

## frtb-common boundary

- [ ] Candidates are package-neutral mechanics only
- [ ] No risk weights, buckets, profiles, capital formulas, or component semantics

## Report completeness

- [ ] `docs/quality/simplification/<date>/<package>.md` uses report template
- [ ] Every finding has scope + P0–P3
- [ ] “What must not move” section present for capital packages
