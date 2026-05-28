# IMA coverage policy

The interim IMA calculation-quality gate is a 90% line-coverage floor for every
module under `packages/frtb-ima/src/frtb_ima`, excluding `demo_data.py`.
`demo_data.py` is demonstration plumbing and is not part of the calculation
coverage gate.

The root `make test` target writes `dist/coverage/frtb-ima.json` and runs
`scripts/ci/check_module_coverage.py` to enforce the per-module floor. The CI
test matrix uses the same target, so a pull request fails if any measured IMA
module drops below 90%.

The later production-quality target is stricter: after the reference-vector,
validation-pack, and independent benchmark follow-ups land, calculation-core
modules should be near or above 95%. Any calculation module below that level
must carry a documented rationale plus mutation-testing and reference-test
evidence showing that residual coverage risk is acceptable.
