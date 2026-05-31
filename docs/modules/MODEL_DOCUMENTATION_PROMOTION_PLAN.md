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
| `frtb-sbm` | 3 | Multiple delta/vega slices implemented; curvature aggregation still pending |

## Current status

| Package | Pack location | Status |
| --- | --- | --- |
| `frtb-ima` | `docs/modules/frtb-ima/model_documentation/` | Complete reference pack |
| `frtb-rrao` | validation docs + module README | Strong validation evidence; formal pack promotion optional |
| `frtb-drc` | `docs/modules/frtb-drc/model_documentation/` | **Started** — intended-use section added in this follow-up |
| `frtb-cva` | planning docs only | Gap checklist below |
| `frtb-sbm` | planning docs only | Gap checklist below |

## Gap checklist — DRC

- [x] `00_intended_use.md` — non-securitisation scope and fail-closed securitisation paths
- [ ] `01_conceptual_soundness.md` — JTD, HBR, bucket/category aggregation citations
- [ ] `02_derivation.md` — gross JTD, maturity scaling, netting walkthrough
- [ ] `03_assumptions_and_limitations.md` — securitisation non-CTP/CTP unsupported
- [ ] `04_validation_evidence.md` — golden fixtures and reconciliation tests
- [ ] `05_monitoring_plan.md` — drift checks on fixture hashes and public API
- [ ] `06_change_history.md` — ADR-linked material changes

## Gap checklist — CVA

- [ ] Intended use differentiating Reduced BA-CVA vs SA-CVA GIRR delta scope
- [ ] Conceptual soundness for MAR50.14 portfolio formula and SA-CVA bucket aggregation
- [ ] Explicit unsupported hedge-recognition and non-GIRR SA-CVA classes
- [ ] Fixture workflow references (`test_sa_cva_fixture_workflow.py`, BA-CVA tests)

## Gap checklist — SBM

- [ ] Intended use for implemented delta/vega slices vs pending curvature
- [ ] Per risk-class scope matrix aligned with `package_maturity.toml`
- [ ] Unsupported CSR securitisation fail-closed behaviour
- [ ] Benchmark and fixture evidence for implemented slices

## Maturity gate interaction

Do not raise a package to `implemented` in `package_maturity.toml` until the
validation evidence sections above are real rather than placeholders. Partial
runtime packages may ship incremental documentation as their supported paths
expand.
