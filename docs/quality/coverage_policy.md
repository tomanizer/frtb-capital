# Implemented- and partial-runtime coverage policy

## Implemented packages (enforced today)

The implemented-package calculation-quality gate is a 90% line-coverage floor
for every top-level module under each package marked `implemented` in
`docs/quality/package_maturity.toml`. The current implemented packages are
`frtb-ima` and `frtb-rrao`.

`demo_data.py` is excluded where present because it is demonstration plumbing
and is not part of the calculation coverage gate.

The root `make test` target writes
`dist/coverage/implemented-packages.json` with coverage for all implemented
packages and runs `scripts/ci/check_module_coverage.py` to enforce the
per-module floor. The CI test matrix uses the same target, so a pull request
fails if any measured implemented-package module drops below 90%.

The later production-quality target is stricter: after the reference-vector,
validation-pack, and independent benchmark follow-ups land, calculation-core
modules should be near or above 95%. Any calculation module below that level
must carry a documented rationale plus mutation-testing and reference-test
evidence showing that residual coverage risk is acceptable.

## Partial-runtime packages (graduated enforcement)

Partial-runtime packages may contain substantive calculation paths before they
reach `implemented` maturity. Coverage enforcement expands gradually so gates
stay tied to stable public runtime slices.

| Maturity trigger | Coverage action |
| --- | --- |
| `partial_runtime` with deterministic public API and golden fixtures | Document intended source roots in this file; **report-only** via `make test-partial-runtime-coverage` |
| First partial-runtime slice promoted to `implemented` | Add package to `make test` enforcement list and maturity registry evidence |
| Package-specific ADR for a new runtime slice | Update excluded modules or floor exceptions with cited rationale |

### Planned partial-runtime candidates

| Package | Ready roots | Gate status |
| --- | --- | --- |
| `frtb-drc` | `packages/frtb-drc/src/frtb_drc` non-securitisation path | report-only; enforce when securitisation scope or maturity promotion lands |
| `frtb-cva` | Reduced BA-CVA and SA-CVA GIRR delta modules | report-only |
| `frtb-sbm` | Implemented delta/vega risk-class modules | report-only until curvature aggregation scope is stable |

Report-only coverage uses the same 90% floor metric but does not fail CI.
Inspect output before raising a package to `implemented`.

## Commands

```bash
make test                         # enforced implemented-package coverage
make test-partial-runtime-coverage  # report-only partial-runtime coverage
python3 scripts/ci/check_module_coverage.py dist/coverage/partial-runtime.json \
  --registry docs/quality/package_maturity.toml --maturity partial_runtime
```

See also [`PACKAGE_STATUS.md`](PACKAGE_STATUS.md) for maturity registry
alignment.
