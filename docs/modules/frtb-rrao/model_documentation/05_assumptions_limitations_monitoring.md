# Assumptions, Limitations, And Monitoring

## Assumptions

| Area | Assumption | Evidence |
| --- | --- | --- |
| Classification evidence | Classification is supplied as canonical evidence; free-form product text is not authoritative. | `validation.py`, `classification.py`, `REGULATORY_ASSUMPTIONS.md`. |
| Gross effective notional | Inputs are non-negative finite gross effective notionals after adapter normalisation. | `validation.py`, `tests/test_validation.py`. |
| Additive capital | Included line add-ons are simple notional times cited risk weight. | `capital.py`, `tests/test_capital.py`. |
| Exclusions | Exclusions are cited zero-capital audit lines, not dropped rows. | `classification.py`, `capital.py`, `tests/test_exclusions.py`. |
| Reconciliation tolerance | Hybrid `rel_tol=1e-12`, `abs_tol=1e-9` reconciles totals; excluded add-ons must be zero within `1e-12`. | `numeric.py`, `tests/test_reconciliation_tolerance.py`. |

## Material Limitations

| Limitation | Current behavior | Evidence |
| --- | --- | --- |
| Investment-fund look-through | U.S. NPR investment-fund inclusion requires a non-look-through portion; `look_through_available=True` is rejected. | `validation.py` look-through checks around lines 429-435; `REGULATORY_ASSUMPTIONS.md`. |
| PRA UK CRR | PRA profile fails closed until UK-specific source mapping and fixtures exist. | `regimes.py` unsupported profile mapping around lines 77-78. |
| U.S. NPR status | U.S. NPR 2.0 is proposed-rule material and results warn callers not to treat output as final regulatory capital. | `scaffold.py` warning around lines 116-118. |
| Production validation | Automated tests and fixtures evidence mechanics only. | This pack; issue #119 audit record. |
| SA composition | `frtb-rrao` does not assemble SBM + DRC + RRAO SA total. | `frtb-orchestration` owns SA composition. |

## Monitoring

| Control | Frequency | Evidence |
| --- | --- | --- |
| Unit, integration, replay, property tests | Every PR | `uv run pytest packages/frtb-rrao`. |
| Lint and typecheck | Every PR | `make lint`, `make typecheck`. |
| Docs and requirement registry checks | Every PR | `make docs-check`. |
| Target-scale benchmark | Material performance changes | `make rrao-benchmark`, `PERFORMANCE.md`. |
| Mutation baseline | Release or scheduled quality review | `make mutation-rrao`, `docs/quality/frtb-rrao/`. |
| Requirement inventory review | Release and material model change | `../../../../packages/frtb-rrao/docs/requirements/BASEL_FRTB_RRAO.yml`. |

## Change Control

Material changes must update code, tests, traceability docs, requirements
registry, and this pack in the same PR. Changes to formulas, supported
profiles, risk weights, exclusion logic, or replay payload semantics should
also update ADRs or release notes where required by `CONTRIBUTING.md`.
