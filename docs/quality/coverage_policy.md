# Implemented-package coverage policy

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
