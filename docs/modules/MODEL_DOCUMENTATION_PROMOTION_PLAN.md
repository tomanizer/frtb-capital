# Model documentation promotion plan

Parent tracker: [#224](https://github.com/tomanizer/frtb-capital/issues/224).

IMA and RRAO already follow the intended model-documentation pack structure
under `docs/modules/frtb-ima/model_documentation/`. Partial-runtime components
should adopt the same sections as their public calculation paths mature.

## Target pack structure

Each component should eventually provide:

1. Intended use and out-of-scope uses
2. Conceptual soundness and regulatory anchors
3. Methodology / derivation
4. Assumptions and limitations (explicit unsupported paths)
5. Validation evidence and monitoring plan
6. Change history

Outputs remain prototype model-validation evidence, not final regulatory
capital or supervisory approval.

## Promotion priority

| Package | Priority | Rationale |
| --- | --- | --- |
| `frtb-drc` | 1 | Non-securitisation path is the most mature partial-runtime slice with fixtures and reconciliation tests |
| `frtb-cva` | 2 | Reduced BA-CVA and SA-CVA GIRR delta paths are deterministic with fixture workflows |
| `frtb-sbm` | 3 | Multiple delta/vega slices and row-wise curvature are implemented; high-volume curvature handoffs and model documentation remain gaps |

## Current status

| Package | Pack location | Status |
| --- | --- | --- |
| `frtb-ima` | `docs/modules/frtb-ima/model_documentation/` | Complete reference pack |
| `frtb-rrao` | validation docs + module README | Strong validation evidence; formal pack promotion optional |
| `frtb-drc` | `docs/modules/frtb-drc/model_documentation/` | Complete partial-runtime pack for current supported paths |
| `frtb-cva` | `docs/modules/frtb-cva/model_documentation/` | Complete partial-runtime pack for current supported paths |
| `frtb-sbm` | `docs/modules/frtb-sbm/model_documentation/` | Complete partial-runtime pack for current supported paths |

## Gap checklist — DRC

- [x] `00_intended_use.md` — non-securitisation scope and fail-closed securitisation paths
- [x] `01_conceptual_soundness.md` — JTD, HBR, bucket/category aggregation citations
- [x] `02_derivation.md` — gross JTD, maturity scaling, netting walkthrough
- [x] `03_assumptions_and_limitations.md` — securitisation non-CTP/CTP unsupported
- [x] `04_validation_evidence.md` — golden fixtures and reconciliation tests
- [x] `05_monitoring_plan.md` — drift checks on fixture hashes and public API
- [x] `06_change_history.md` — ADR-linked material changes

## Gap checklist — CVA

- [x] Intended use differentiating Reduced BA-CVA vs SA-CVA scope
- [x] Conceptual soundness for MAR50.14 portfolio formula and SA-CVA bucket aggregation
- [x] Explicit unsupported hedge-recognition and unsupported runtime paths
- [x] Fixture workflow references (`test_cva_sa_cva_fixture_workflow.py`, BA-CVA tests)

## Gap checklist — SBM

- [x] Intended use for implemented delta/vega/row-wise, batch, and Arrow curvature slices
- [x] Per risk-class scope matrix aligned with `package_maturity.toml`
- [x] Unsupported SBM sub-feature and profile fail-closed behaviour
- [x] Benchmark and fixture evidence for implemented slices

## Maturity gate interaction

Do not raise a package to `implemented` in `package_maturity.toml` until the
validation evidence sections above are real rather than placeholders. Partial
runtime packages may ship incremental documentation as their supported paths
expand.
