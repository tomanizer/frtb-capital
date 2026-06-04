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

Outputs are engineering and validation evidence, not final regulatory capital.
`PACKAGE_METADATA.validation_status` remains `PENDING`.

**Integration journey (Arrow per class → capital → attribution → SA/suite/store):**
[`docs/PACKAGE_JOURNEY.md`](docs/PACKAGE_JOURNEY.md)

## Documentation

| Document | Purpose |
| --- | --- |
| [PACKAGE_JOURNEY.md](docs/PACKAGE_JOURNEY.md) | End-to-end client flow, row vs batch semantics, profile/class routing, orchestration boundaries |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Capital attribution method, inputs, supported grains, and limitations |
| [PUBLIC_API.md](../../docs/modules/frtb-drc/PUBLIC_API.md) | Stable client integration surface and Arrow paths |
| [PROFILE_SUPPORT_MATRIX.md](../../docs/modules/frtb-drc/PROFILE_SUPPORT_MATRIX.md) | Profile and risk-class support status |
| [Module README](../../docs/modules/frtb-drc/README.md) | Planning pack, model documentation, requirements |
| [REGULATORY_REQUIREMENTS.md](../../docs/modules/frtb-drc/REGULATORY_REQUIREMENTS.md) | Regulatory requirement mapping (module docs) |
| [Requirement registry](docs/requirements/BASEL_FRTB_DRC.yml) | Package-local machine-readable implementation status |
| [Dataset contract](docs/DATASET_CONTRACT.md) | Package-local synthetic fixture contract |
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

## End-to-end examples

See `examples/run_demo.py` for a self-contained quick-start that:

- Loads the committed 40-position non-securitisation v2 fixture (exercises every
  material mechanic: gross JTD tiers, maturity ladder, accepted/rejected netting
  by seniority rank, HBR, P&L flooring, defaulted LGD=100% override).
- Calls the public `calculate_drc_capital`.
- Prints total/category/bucket capital + rejected offsets (for attribution).
- Shows a minimal raw `DrcPosition(...)` construction so you can see the exact
  fields an upstream system must provide.

```bash
uv run python packages/frtb-drc/examples/run_demo.py
```

The fixture loader + golden expected outputs live under `tests/fixtures/drc_nonsec_v2/`
(manifest + positions.json + expected_outputs.json). The source generator is
`src/frtb_drc/demo_data.py`.

For step-by-step regulatory mechanics with visuals, run the notebooks/:

- 00_validation_map.ipynb
- 01_gross_jtd.ipynb ... 05_category_capital.ipynb

See `docs/REGULATORY_TRACEABILITY.md`, `docs/REGULATORY_ASSUMPTIONS.md`, and
`docs/regulatory_sources.yml` (plus the modules/ planning pack) for citations
and scope. The package also supports Arrow/batch handoff for high-volume paths.
