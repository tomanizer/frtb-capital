# Validation Evidence

`frtb-cva` has `ValidationStatus.AVAILABLE` for the package-owned calculation
scope: deterministic BA-CVA, SA-CVA, mixed carve-out, profile, batch, Arrow,
audit, replay, attribution, and public-API mechanics over synthetic canonical
inputs. The evidence below supports the repository-level `implemented` maturity
status. It is not evidence of bank source-data quality, legal interpretation,
supervisory approval, production monitoring, or final regulatory capital.

## Fixture Evidence

| Fixture or test | Scope | Evidence |
| --- | --- | --- |
| `packages/frtb-cva/tests/fixtures/ba_cva_reduced_v1/` | Reduced BA-CVA | Synthetic single-counterparty cases with committed challenger outputs derived from MAR50.14-MAR50.16 scalars, risk weights, maturity, EAD, discount factor, and alpha. |
| `packages/frtb-cva/tests/fixtures/profile_comparison_v1/` | Non-Basel comparison profiles | Source-id, citation-id, support-matrix, reference-payload, and deterministic content-hash evidence for `US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` BA-CVA and SA-CVA comparison paths. |
| `packages/frtb-cva/tests/fixtures/sa_cva_girr_delta_v1/` | SA-CVA GIRR delta | GIRR delta buckets, eligible hedge offset, ineligible hedge rejection, invalid tenor cases, and deterministic replay. |
| `packages/frtb-cva/tests/test_cva_ba_cva_fixture_workflow.py` | BA-CVA fixture workflow | Reduced BA-CVA fixture loading, expected standalone SCVA, reduced portfolio capital, audit payloads, invalid-case failures, and determinism. |
| `packages/frtb-cva/tests/test_cva_profile_evidence_fixture.py` | Profile fixture workflow | Committed profile evidence is checked against runtime profile hashes, reference payloads, citation source ids, regulatory crosswalk source refs, support-matrix method/path rows, and fail-closed unsupported cells. |
| `packages/frtb-cva/tests/test_cva_sa_cva_fixture_workflow.py` | SA-CVA fixture workflow | Expected capital, weighted-sensitivity payloads, invalid-case failures, and determinism. |
| `packages/frtb-cva/tests/test_cva_arrow_batch.py` | Arrow and batch boundary | Row/batch/handoff parity for BA-CVA and SA-CVA fixture cases. |
| `packages/frtb-cva/tests/test_cva_unsupported_features.py` | Profile comparison runs | `US_NPR20_VB`, `EU_CRR3_CVA`, and `UK_PRA_CVA` public API runs assert profile-owned citations and hashes for BA-CVA, SA-CVA, mixed carve-out, hedge handling, and batch paths. |

## Unit, Property, And Comparator Evidence

- `test_cva_ba_cva_reduced.py` includes an independent MAR50.14 oracle.
- `test_cva_ba_cva_full.py`, `test_cva_hedges.py`, and
  `test_cva_scope.py` cover hedge and method routing.
- `tests/risk_classes/` covers implemented SA-CVA GIRR, FX, CCS, RCS, equity,
  and commodity paths.
- `test_cva_properties.py` checks monotonicity and hedge-benefit properties.
- `test_cva_external_comparator.py` protects the supported slice against a
  committed comparator.
- `test_cva_regimes.py`, `test_cva_reference_data.py`,
  `test_cva_profile_evidence_fixture.py`, and `test_cva_support_matrix.py`
  check profile hashes, profile-specific citation maps, source manifests,
  supported profile/method/path rows, and fail-closed unsupported cells.
- `test_cva_unsupported_features.py` checks fail-closed unsupported runtime
  paths.
- `test_cva_implemented_guardrails.py` checks promoted implemented-package
  guardrails across batch column coercion, profile metadata, scope routing, and
  qualified-index fail-closed behavior.

## Audit, Replay, And Reconciliation Evidence

- `test_cva_public_api.py` checks public result reconciliation, stable input
  hashes, JSON-ready serialization, and full BA-CVA public-path assembly.
- `test_cva_audit.py` checks audit serialization, input hashing, source-lineage
  payloads, unsupported flags, and result reconciliation invariants, including
  tampered-result rejection.
- `test_cva_replay.py` checks deterministic replay from serialized audit
  records.
- `test_cva_batch_calculations.py`, `test_cva_arrow_batch.py`, and
  `test_cva_payloads.py` check row, batch, Arrow, and payload parity across the
  package-owned handoff boundary.

## Accepted Out-Of-Scope Validation Limits

The following limits are deliberate boundaries, not blockers for repository
`implemented` maturity:

- bank source-data controls and production lineage certification before
  canonical CVA inputs reach the package;
- legal interpretation of proposed or jurisdiction-specific rules beyond the
  cited profile crosswalks;
- supervisory approval for SA-CVA model use;
- supervisory benchmark or bank portfolio backtesting against proprietary data;
- production monitoring history after deployment;
- MAR50.9 and analogous simplified CCR-substitution alternatives, which remain
  fail-closed because they require external CCR capital and orchestration method
  election.
