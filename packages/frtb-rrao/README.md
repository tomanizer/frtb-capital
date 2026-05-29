# frtb-rrao

Standardised Approach residual risk add-on component.

The package is importable and exposes a public canonical-input calculation
boundary for supported Basel MAR23, U.S. NPR 2.0, and EU CRR3 comparison
profile slices. Unsupported profiles and unsupported evidence paths fail
explicitly; the package must not emit zero or placeholder capital for
unsupported scope.

The v1 implementation path covers U.S. NPR 2.0 proposed section `__.211`,
Basel MAR23 additive line-capital mechanics, and EU Article 325u / Delegated
Regulation (EU) 2022/2328 comparison mappings, with classification evidence and
exclusions recorded in audit output.

The U.S. NPR 2.0 profile also supports proposed section `__.211(a)(3)`
investment-fund inclusion when the input supplies an explicit
`__.205(e)(3)(iii)` backstop-method descriptor and cited mandate evidence.

The EU CRR3 comparison profile maps Delegated Regulation (EU) 2022/2328
Article 1 exotic underlyings, Article 2 Annex instruments, and Article 3
non-presumptive risks for canonical inputs. PRA UK CRR remains unsupported
until package-local source mapping and fixtures are added.

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
