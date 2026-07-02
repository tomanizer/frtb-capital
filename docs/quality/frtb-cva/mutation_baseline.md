# CVA Mutation Testing Baseline

Date: 2026-07-02

Issue: #1148, parent epic #1150

## Scope

Mutation testing is configured for the CVA BA-CVA and SA-CVA calculation
boundary:

- `packages/frtb-cva/src/frtb_cva/ba_cva.py`
- `packages/frtb-cva/src/frtb_cva/capital.py`
- `packages/frtb-cva/src/frtb_cva/kernel/ba_full.py`
- `packages/frtb-cva/src/frtb_cva/kernel/ba_reduced.py`
- `packages/frtb-cva/src/frtb_cva/kernel/sa.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/ccs.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/commodity.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/equity.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/fx.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/girr.py`
- `packages/frtb-cva/src/frtb_cva/risk_classes/rcs.py`
- `packages/frtb-cva/src/frtb_cva/sa_cva.py`
- `packages/frtb-cva/src/frtb_cva/weighted_sensitivity.py`

The package-local `mutmut` configuration lives in
`packages/frtb-cva/pyproject.toml`. The root `make mutation-cva` target runs the
package-local configuration with `HYPOTHESIS_PROFILE=dev` and preloads NumPy
before invoking mutmut, matching the IMA target's in-process NumPy reload
workaround.

Mutation is intentionally excluded for adapter, batch, audit, CRIF, and
reference-data support surfaces. This baseline is for capital calculation
kernels and public calculation assembly, not IO or serialization plumbing.

## Command

```sh
make mutation-cva
```

## Baseline Result

Tool: `mutmut` 3.5.0

Baseline command completed successfully on 2026-07-02.

| Metric | Count |
| --- | ---: |
| Total mutants | 1,688 |
| Killed | 1,158 |
| Survived | 530 |
| Timeout | 0 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |
| Segfault | 0 |

Killed-only mutation score: `68.60%`.

The initial CVA mutation floor is set to this honest baseline in
`docs/quality/package_maturity.toml`. The score establishes mutation-testing
evidence for CVA; follow-up hardening should raise the floor rather than lower
or re-scope this baseline.

## Module Breakdown

| Module | Total | Killed | Survived | Score |
| --- | ---: | ---: | ---: | ---: |
| `ba_cva.py` | 460 | 319 | 141 | 69.35% |
| `capital.py` | 31 | 17 | 14 | 54.84% |
| `kernel/ba_full.py` | 0 | 0 | 0 | n/a |
| `kernel/ba_reduced.py` | 0 | 0 | 0 | n/a |
| `kernel/sa.py` | 87 | 59 | 28 | 67.82% |
| `risk_classes/ccs.py` | 37 | 20 | 17 | 54.05% |
| `risk_classes/commodity.py` | 62 | 33 | 29 | 53.23% |
| `risk_classes/equity.py` | 62 | 33 | 29 | 53.23% |
| `risk_classes/fx.py` | 90 | 50 | 40 | 55.56% |
| `risk_classes/girr.py` | 34 | 20 | 14 | 58.82% |
| `risk_classes/rcs.py` | 62 | 33 | 29 | 53.23% |
| `sa_cva.py` | 125 | 88 | 37 | 70.40% |
| `weighted_sensitivity.py` | 638 | 486 | 152 | 76.18% |

The two `kernel/ba_*` wrapper modules are in the configured scope but produced
zero covered-line mutants in this run because `mutate_only_covered_lines` is
enabled. They remain listed so future test or wrapper changes do not silently
move the configured boundary.

## Schedule

Mutation testing is not part of the normal push gate because it is slower than
the deterministic package suite. `.github/workflows/mutation.yml` runs it
weekly, exports `mutmut-cicd-stats.json`, and enforces this killed-only
baseline with `scripts/ci/check_mutation_score.py`. It should also be rerun for
material changes to the configured CVA calculation boundary.
