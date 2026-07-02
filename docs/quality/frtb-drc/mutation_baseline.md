# DRC Mutation Testing Baseline

Date: 2026-07-02

Issue: #1147, parent epic #1150

## Scope

Mutation testing is configured for the DRC calculation boundary:

- `packages/frtb-drc/src/frtb_drc/capital.py`
- `packages/frtb-drc/src/frtb_drc/gross_jtd.py`
- `packages/frtb-drc/src/frtb_drc/kernel/ctp.py`
- `packages/frtb-drc/src/frtb_drc/kernel/net_jtd.py`
- `packages/frtb-drc/src/frtb_drc/kernel/nonsec.py`
- `packages/frtb-drc/src/frtb_drc/kernel/securitisation.py`
- `packages/frtb-drc/src/frtb_drc/kernel/securitisation_gross.py`
- `packages/frtb-drc/src/frtb_drc/netting.py`

The package-local `mutmut` configuration lives in
`packages/frtb-drc/pyproject.toml`. The root `make mutation-drc` target runs the
package-local configuration with `HYPOTHESIS_PROFILE=dev` and preloads NumPy
before invoking mutmut, matching the IMA target's in-process NumPy reload
workaround.

Mutation is intentionally excluded for adapter, batch, audit, CRIF, and
reference-data support surfaces. This baseline is for default-risk charge
calculation kernels and public calculation assembly, not IO or serialization
plumbing.

## Command

```sh
make mutation-drc
```

## Baseline Result

Tool: `mutmut` 3.5.0

Baseline command completed successfully on 2026-07-02.

| Metric | Count |
| --- | ---: |
| Total mutants | 2,315 |
| Killed | 1,927 |
| Survived | 388 |
| Timeout | 0 |
| No tests | 0 |
| Skipped | 0 |
| Suspicious | 0 |
| Segfault | 0 |

Killed-only mutation score: `83.24%`.

The initial DRC mutation floor is set to this honest baseline in
`docs/quality/package_maturity.toml`. The score establishes mutation-testing
evidence for DRC; follow-up hardening should raise the floor rather than lower
or re-scope this baseline.

## Module Breakdown

| Module | Total | Killed | Survived | Score |
| --- | ---: | ---: | ---: | ---: |
| `capital.py` | 254 | 221 | 33 | 87.01% |
| `gross_jtd.py` | 155 | 136 | 19 | 87.74% |
| `kernel/ctp.py` | 714 | 567 | 147 | 79.41% |
| `kernel/net_jtd.py` | 0 | 0 | 0 | n/a |
| `kernel/nonsec.py` | 90 | 83 | 7 | 92.22% |
| `kernel/securitisation.py` | 639 | 521 | 118 | 81.53% |
| `kernel/securitisation_gross.py` | 131 | 109 | 22 | 83.21% |
| `netting.py` | 332 | 290 | 42 | 87.35% |

The `kernel/net_jtd.py` wrapper module is in the configured scope but produced
zero covered-line mutants in this run because `mutate_only_covered_lines` is
enabled. It remains listed so future test or wrapper changes do not silently
move the configured boundary.

## Schedule

Mutation testing is not part of the normal push gate because it is slower than
the deterministic package suite. `.github/workflows/mutation.yml` runs it
weekly, exports `mutmut-cicd-stats.json`, and enforces this killed-only
baseline with `scripts/ci/check_mutation_score.py`. It should also be rerun for
material changes to the configured DRC calculation boundary.
