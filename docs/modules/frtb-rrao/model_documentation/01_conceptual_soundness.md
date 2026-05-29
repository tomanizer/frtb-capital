# Conceptual Soundness

## Model Design

RRAO is an additive capital component. The package therefore separates:

- canonical input validation in `validation.py`;
- cited classification and exclusion decisions in `classification.py` and
  `reference_data.py`;
- line-level add-on construction and deterministic subtotals in `capital.py`;
- replay, hashing, serialization, and reconciliation in `audit.py`;
- optional allocation reports in `allocation.py`.

This split is conceptually appropriate because Basel MAR23.8 and proposed
section `__.211(c)` calculate capital from gross effective notional and a
regulatory risk weight, while MAR23.2-MAR23.7 and proposed `__.211(a)`-
`__.211(b)` control which positions are included or excluded.

## Core Components

| Component | Evidence | Regulatory anchor |
| --- | --- | --- |
| Canonical input contracts | `data_models.py`, `validation.py`, `tests/test_validation.py` | Basel MAR23.8; proposed `__.211(c)(2)`. |
| Rule profiles | `regimes.py`, `reference_data.py`, `tests/test_regimes.py`, `tests/test_reference_data.py` | Basel MAR23.2-MAR23.8; proposed `__.211`; Article 325u; Delegated Regulation 2022/2328. |
| Classification and exclusions | `classification.py`, `tests/test_classification.py`, `tests/test_exclusions.py` | Basel MAR23.2-MAR23.7; proposed `__.211(a)`-`__.211(b)`. |
| Capital add-ons | `capital.py`, `tests/test_capital.py` | Basel MAR23.8; proposed `__.211(c)(1)`; Article 325u(3). |
| Audit and replay | `audit.py`, `tests/test_audit.py`, `tests/test_replay.py` | Deterministic engineering control supporting review of MAR23 / `__.211` mechanics. |
| Allocation reports | `allocation.py`, `tests/test_allocation.py` | Additive explain output for line, desk, legal-entity, and evidence-type review. |

## Evidence Strength

Evidence is strongest for deterministic calculation mechanics: unit tests,
fixture replay, external comparator tests, property tests, mutation evidence,
and benchmark replay hashes cover the v1 package boundary.

Evidence is weaker for production governance that requires bank portfolios,
legal interpretation, independent model validation, and supervisory approval.
Those limits are recorded in
[`05_assumptions_limitations_monitoring.md`](05_assumptions_limitations_monitoring.md).
