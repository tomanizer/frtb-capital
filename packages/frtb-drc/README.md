# frtb-drc

Standardised Approach default risk charge component for the `frtb-capital`
suite.

## Status

The package exposes `calculate_drc_capital` for supported U.S. NPR 2.0
non-securitisation, securitisation non-CTP, and correlation trading portfolio
(CTP) paths, plus cited Basel MAR22 non-securitisation and securitisation
non-CTP paths. EU CRR3 and PRA_UK_CRR profile identities are known but fail
closed until cited mappings exist. Unsupported scope must not emit zero or
placeholder capital.

| Area | Status |
| --- | --- |
| U.S. NPR 2.0 non-sec / sec non-CTP / CTP | Implemented row and Arrow batch paths |
| Basel MAR22 non-sec / sec non-CTP | Implemented row and Arrow batch paths |
| Basel MAR22 CTP | Fail-closed until cited contracts land |
| EU CRR3 / PRA_UK_CRR | Fail-closed profile identities |

Outputs are prototype engineering evidence, not final regulatory capital.
`PACKAGE_METADATA.validation_status` remains `PENDING`.

## Documentation

| Document | Purpose |
| --- | --- |
| [PUBLIC_API.md](../../docs/modules/frtb-drc/PUBLIC_API.md) | Stable client integration surface and Arrow paths |
| [PROFILE_SUPPORT_MATRIX.md](../../docs/modules/frtb-drc/PROFILE_SUPPORT_MATRIX.md) | Profile and risk-class support status |
| [Module README](../../docs/modules/frtb-drc/README.md) | Planning pack, model documentation, requirements |
| [REGULATORY_REQUIREMENTS.md](../../docs/modules/frtb-drc/REGULATORY_REQUIREMENTS.md) | Regulatory requirement mapping (module docs) |
| [CLIENT_REFERENCE_DATA.md](../../docs/CLIENT_REFERENCE_DATA.md) | Run-scoped risk-weight and overlay rules |

## Public API

```python
from frtb_drc import PACKAGE_METADATA, calculate_drc_capital
```

High-volume paths use class-specific Arrow normalizers and batch builders
documented in [`PUBLIC_API.md`](../../docs/modules/frtb-drc/PUBLIC_API.md).

Securitisation non-CTP and CTP risk weights and replication/decomposition
evidence are supplied in `DrcCalculationContext` as run-scoped maps. Missing
risk weights, incomplete fair-value cap evidence, unsupported decomposition
evidence, and unmapped profiles fail closed.

See `AGENTS.md` for package boundary rules.