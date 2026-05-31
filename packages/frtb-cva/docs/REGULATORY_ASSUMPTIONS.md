# CVA regulatory assumptions

## Scope

These assumptions apply to the delivered reduced BA-CVA and SA-CVA GIRR delta
slice. They do not represent final regulatory capital or model approval status.

## Calibration

- Basel MAR50 July 2020 revision: `D_BA-CVA = 0.65` (MAR50.14).
- SA-CVA multiplier `m_CVA = 1.0` (MAR50.53).
- SA-CVA hedging-disallowance scalar `R = 0.01` (MAR50.55); see
  [ADR 0016](../../../docs/decisions/0016-cva-sa-cva-hedging-disallowance.md).
- GIRR inter-bucket correlation `γ_bc = 0.5` for specified currencies (MAR50.57).
- GIRR specified-currency set: `{USD, EUR, GBP, AUD, CAD, SEK, JPY}` (MAR50.54).
- Other-currency GIRR delta risk-weight scalar `1.4×` (MAR50.57).

## Discount factor policy

- IMM netting sets use `DF_NS = 1.0` (MAR50.15(4)).
- Non-IMM netting sets may supply an explicit positive discount factor; when the
  supplied value is the profile default sentinel `1.0`, the package computes
  `(1 - exp(-0.05 * M)) / (0.05 * M)`.

## Inputs

- Counterparty sector and credit quality must map to Table 1 (MAR50.16).
- EAD sign convention: `non_negative` or `signed_absolute`; amounts must be
  finite and non-negative after normalisation.
- SA-CVA sensitivity sign convention: `positive_loss` or `signed_absolute`.
- SA-CVA GIRR delta sensitivities require a cited tenor label.
- SA-CVA capital calculation rejects counterparty and netting-set inputs; pass
  sensitivities (and optional hedges) only.

## Explicit non-goals

- No CRIF/vendor adapters in the core runtime path.
- No sibling capital-package imports.
- No placeholder successful capital for unsupported methods.
