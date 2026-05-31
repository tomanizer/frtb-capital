# CVA regulatory assumptions

## Scope

These assumptions apply to the phase 1 reduced BA-CVA slice only. They do not
represent final regulatory capital or model approval status.

## Calibration

- Basel MAR50 July 2020 revision: `D_BA-CVA = 0.65`.
- SA-CVA reference tables store `m_CVA = 1.0` for future slices; SA-CVA capital
  is not calculated in phase 1.

## Discount factor policy

- IMM netting sets use `DF_NS = 1.0` (MAR50.15(4)).
- Non-IMM netting sets may supply an explicit positive discount factor; when the
  supplied value is the profile default sentinel `1.0`, the package computes
  `(1 - exp(-0.05 * M)) / (0.05 * M)`.

## Inputs

- Counterparty sector and credit quality must map to Table 1 (MAR50.16).
- EAD must be finite and non-negative before capital calculation.
- SA-CVA sensitivities and hedges are validated but not capital-producing in
  phase 1.

## Explicit non-goals

- No CRIF/vendor adapters in the core runtime path.
- No sibling capital-package imports.
- No placeholder successful capital for unsupported methods.
