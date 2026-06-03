# Derivation

## BA-CVA

Reduced BA-CVA computes netting-set supervisory CVA terms from exposure,
maturity, risk weight, and supervisory discounting inputs, then assembles the
portfolio charge with the MAR50.14 formula. The July 2020 Basel calibration uses
`D_BA-CVA = 0.65` under MAR50.14. Counterparty Table 1 risk weights are anchored
to MAR50.16.

Full BA-CVA adds hedge recognition under MAR50.17-MAR50.26. Hedge eligibility is
validated before benefit is applied; ineligible hedges remain present in audit
records but do not reduce capital.

## SA-CVA

SA-CVA starts from aggregate CVA and hedge sensitivities under MAR50.47. The
package computes weighted sensitivities, applies risk-class bucket rules under
MAR50.54-MAR50.77, and aggregates bucket capital under MAR50.53 and
MAR50.55-MAR50.57. Hedge sensitivities are netted with the MAR50.52 sign
treatment so eligible bought protection offsets positive regulatory CVA
sensitivities.

Supported vega paths require explicit volatility inputs where MAR50 defines
`RW_k = RW_sigma * sigma_k`; missing volatility fails validation.

## Mixed Method

Mixed SA-CVA plus BA-CVA carve-out assembly applies SA-CVA to in-scope
sensitivity inputs and BA-CVA to carved-out netting sets. The routing is tied to
MAR50.8 and records method-specific components in the result so orchestration can
aggregate without reinterpreting CVA internals.

## Audit And Attribution

Capital results carry deterministic profile/input hashes, branch metadata, and
method-specific components. Attribution and impact helpers preserve capital
totals and label unsupported nonlinear branches rather than emitting placeholder
successful capital.
