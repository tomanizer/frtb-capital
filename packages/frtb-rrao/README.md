# frtb-rrao

Standardised Approach residual risk add-on component.

The package is importable and exposes a public canonical-input calculation
boundary for supported Basel MAR23 and U.S. NPR 2.0 profile slices. Unsupported
profiles and unsupported evidence paths fail explicitly; the package must not
emit zero or placeholder capital for unsupported scope.

The v1 implementation path covers U.S. NPR 2.0 proposed section `__.211` and
Basel MAR23 additive line-capital mechanics, with classification evidence and
exclusions recorded in audit output.

Planning documents:

- [Model documentation](../../docs/modules/frtb-rrao/MODEL_DOCUMENTATION.md)
- [Detailed requirements](../../docs/modules/frtb-rrao/DETAILED_REQUIREMENTS.md)
- [Architecture and data design](../../docs/modules/frtb-rrao/ARCHITECTURE_AND_DATA_DESIGN.md)
- [Decisions and implementation plan](../../docs/modules/frtb-rrao/DECISIONS_AND_PLAN.md)
- [Workable issue breakdown](../../docs/modules/frtb-rrao/ISSUE_BREAKDOWN.md)

Package-local regulatory documentation:

- [Regulatory traceability](docs/REGULATORY_TRACEABILITY.md)
- [Regulatory assumptions](docs/REGULATORY_ASSUMPTIONS.md)
- [Regulatory sources](docs/regulatory_sources.yml)
