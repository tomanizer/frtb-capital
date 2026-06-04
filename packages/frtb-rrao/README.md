# frtb-rrao

Standardised Approach residual risk add-on component.

The package is importable and exposes a public canonical-input calculation
boundary for supported Basel MAR23, U.S. NPR 2.0, EU CRR3 comparison, and
PRA_UK_CRR profile slices. Unsupported profiles and unsupported evidence paths fail
explicitly; the package must not emit zero or placeholder capital for
unsupported scope.

The v1 implementation path covers U.S. NPR 2.0 proposed section `__.211`,
Basel MAR23 additive line-capital mechanics, and EU Article 325u / Delegated
Regulation (EU) 2022/2328 comparison mappings, with classification evidence and
exclusions recorded in audit output.

The U.S. NPR 2.0 profile also supports proposed section `__.211(a)(3)`
investment-fund inclusion when the input supplies an explicit
`__.205(e)(3)(iii)` backstop-method descriptor and cited mandate evidence.
Exact third-party back-to-back exclusions require deterministic two-transaction
match evidence and remain visible as zero-capital audit lines.

The EU CRR3 comparison profile maps Delegated Regulation (EU) 2022/2328
Article 1 exotic underlyings, Article 2 Annex instruments, and Article 3
non-presumptive risks for canonical inputs.

The PRA_UK_CRR profile maps UK CRR Article 325u and UK retained Delegated
Regulation (EU) 2022/2328 with legislation.gov.uk citations and `rrao_pra`
fixture replay. Investment-fund inclusion remains fail-closed for PRA, as for EU.

**Integration journey (Arrow → capital → allocation → SA/suite/store):**
[`docs/PACKAGE_JOURNEY.md`](docs/PACKAGE_JOURNEY.md)

Planning documents:

- [Model documentation](../../docs/modules/frtb-rrao/MODEL_DOCUMENTATION.md)
- [IMA-style evidence pack](../../docs/modules/frtb-rrao/model_documentation/README.md)
- [Stable public API](../../docs/modules/frtb-rrao/PUBLIC_API.md)
- [Detailed requirements](../../docs/modules/frtb-rrao/DETAILED_REQUIREMENTS.md)
- [Architecture and data design](../../docs/modules/frtb-rrao/ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](../../docs/modules/frtb-rrao/DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](../../docs/modules/frtb-rrao/ISSUE_BREAKDOWN.md)

Package-local regulatory documentation:

- [Package journey](docs/PACKAGE_JOURNEY.md) — end-to-end client flow, tiers, profile/evidence routing, orchestration boundaries
- [Capital attribution](ATTRIBUTION.md) — additive allocation method, supported dimensions, and limitations
- [Regulatory traceability](docs/REGULATORY_TRACEABILITY.md)
- [Regulatory assumptions](docs/REGULATORY_ASSUMPTIONS.md)
- [Regulatory sources](docs/regulatory_sources.yml)
- [Requirement registry](docs/requirements/BASEL_FRTB_RRAO.yml)
- [Dataset contract](docs/DATASET_CONTRACT.md)
- [Performance and replay controls](docs/PERFORMANCE.md)
- [Allocation reports](docs/ALLOCATION.md)
- [Mutation evidence](../../docs/quality/frtb-rrao/mutation_baseline.md)

## End-to-end examples

See `examples/run_demo.py` for a quick-start demo that loads the package's
synthetic sample book fixture and exercises `calculate_rrao_capital` under the
primary US_NPR_2_0 profile, printing totals, exclusion counts, and capital lines.
(Basel/EU multi-profile comparison, including profile-specific exclusions, is
covered in the notebooks and test_eu_profile.py.)

```bash
uv run python packages/frtb-rrao/examples/run_demo.py
```

The `examples/rrao_fixture.py` provides the loader + expected outputs used by
the demo. For deeper classification, allocation, and multi-profile walkthroughs
see the notebooks/ (01-04) and `tests/test_fixture_workflow.py`.
