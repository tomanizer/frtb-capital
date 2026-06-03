# FRTB-IMA PRD

`frtb-ima` is the implemented Internal Models Approach capital package in the
suite. The package should remain one cohesive model package with documented
internal components rather than splitting RFET, PLA, backtesting, stress-period
selection, expected shortfall, SES, or capital assembly into sibling workspace
packages.

## Product Goal

Provide a transparent, deterministic IMA capital layer that consumes validated
scenario P&L, RFET evidence, NMRF stress artifacts, and PLA/backtesting vectors
from upstream risk systems, then produces desk-level IMA capital and audit
evidence.

## Users

- Quant methodology reviewers validating formula choices and regulatory
  traceability.
- Model validators reviewing intended use, limitations, sensitivity analysis,
  monitoring, and change history.
- Engineers integrating package-level outputs into suite orchestration.
- Audit and governance reviewers inspecting reproducibility evidence.

## Functional Requirements

- Calculate empirical expected shortfall and liquidity-horizon adjusted ES.
- Calculate reduced-set ES and IMCC.
- Classify RFET evidence and route modellable and non-modellable risk factors.
- Calculate NMRF stress-scenario capital and SES aggregation.
- Calculate PLA diagnostics and backtesting exception evidence.
- Assemble IMA capital from IMCC, SES, multiplier, and PLA add-on inputs.
- Emit frozen, auditable result records.
- Maintain package-local regulatory traceability and requirement status.

## Non-Goals

- Do not implement market-data sourcing or pricing engines.
- Do not implement SA component capital inside `frtb-ima`.
- Do not make RFET, PLA, stress-period selection, or SES separate workspace
  packages unless a future ADR demonstrates independent reuse and versioning.
- Do not present synthetic engineering or validation outputs as final
  regulatory capital.

## Orchestration Contract

`frtb-orchestration` should consume package-level IMA outputs and desk
eligibility status. It should route non-IMA-eligible desks to the SA component
stack: `frtb-sbm + frtb-drc + frtb-rrao`.
