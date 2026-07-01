# Intended Use

## Model Purpose

`frtb-sbm` calculates Standardised Approach Sensitivities-Based Method capital
for supported Basel MAR21 sensitivity inputs. It consumes prepared delta, vega,
and curvature sensitivities from upstream risk systems and emits auditable
risk-class capital results for Standardised Approach orchestration.

The package does not source market data, calculate trade prices, generate
sensitivities, or compose total Standardised Approach capital. SA composition
belongs in `frtb-orchestration`.

## Supported Scope

The current partial runtime supports `BASEL_MAR21` delta, vega, and row-wise,
batch, and Arrow batch curvature paths for:

- GIRR;
- FX;
- equity;
- commodity;
- CSR non-securitisation;
- CSR securitisation non-CTP;
- CSR securitisation CTP.

The package also supports CRIF/CSV adapter paths where input rows map to the
canonical sensitivity model and preserve source lineage.

The package also supports `US_NPR_2_0` GIRR delta, GIRR vega, and GIRR curvature
as proposed-rule comparison slices under Federal Register 91 FR 14952 section
V.A.7.a and `PRA_UK_CRR` GIRR delta under PRA PS1/26 Appendix 1 / PRA2026/1
Articles 325c, 325h, and 325ae-325ag. All other U.S. NPR 2.0 cells, all EU
CRR3 cells, and all PRA UK CRR cells outside GIRR delta fail closed until
profile-specific citations and deterministic fixtures are added.

Post-calculation attribution is supported for selected, differentiable delta and
vega branches through analytical Euler `CapitalContribution` records. Curvature
and other non-differentiable or incomplete-evidence attribution paths are
reported as unsupported residual records. Baseline-vs-candidate impact is
available as finite difference and is separate from marginal contribution.

## Out Of Scope

- U.S. NPR 2.0 runtime capital outside GIRR delta, GIRR vega, and GIRR curvature;
- EU CRR3 and PRA UK CRR runtime capital;
- market-data sourcing, pricing, and sensitivity generation;
- total SA aggregation across SBM, DRC, and RRAO;
- unsupported curvature sub-features where the package requires additional
  evidence, such as equity repo curvature and FX scalar flags.
