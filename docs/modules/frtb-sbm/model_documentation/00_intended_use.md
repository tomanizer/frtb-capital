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

Post-calculation attribution is supported for selected, differentiable delta and
vega branches through analytical Euler `CapitalContribution` records. Curvature
and other non-differentiable or incomplete-evidence attribution paths are
reported as unsupported residual records. Baseline-vs-candidate impact is
available as finite difference and is separate from marginal contribution.

## Out Of Scope

- U.S. NPR 2.0, EU CRR3, and PRA UK CRR runtime capital;
- market-data sourcing, pricing, and sensitivity generation;
- total SA aggregation across SBM, DRC, and RRAO;
- unsupported curvature sub-features where the package requires additional
  evidence, such as equity repo curvature and FX scalar flags.
