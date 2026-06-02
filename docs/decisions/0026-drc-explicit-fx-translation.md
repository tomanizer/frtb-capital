# 26. DRC explicit FX translation into base currency

Date: 2026-06-02

## Status

Accepted

## Context

Issue #338 identified that `frtb-drc` rejected any position whose native
currency differed from `DrcCalculationContext.base_currency`. That made a
realistic multi-currency default-risk book impossible to calculate in one DRC
run, even though proposed section `__.210(a)` requires a single default-risk
capital calculation over covered default-risk positions and proposed section
`__.210(b)(1)(iii)` defines gross default exposure from notional amount or face
value and cumulative P&L.

The U.S. NPR DRC text does not add a separate DRC-only FX sourcing mechanism.
The broader market-risk proposed rule requires standardized market-risk
calculations in the banking organization's reporting currency in proposed
section `__.207(a)(8)`, except for the approved FX base-currency case, and uses
spot reporting/base exchange rates for FX risk factors in proposed section
`__.208(h)(1)(ii)`. The package therefore needs an explicit, auditable
translation convention rather than silent per-currency rejection or implicit
rate lookup.

## Decision

`frtb-drc` will accept multi-currency non-securitisation books only when the
calculation context supplies explicit FX rates for every non-base input
currency. Each rate is represented as a frozen `DrcFxRate` with:

- source currency and target/base currency;
- finite positive rate;
- as-of date equal to the calculation date;
- source id;
- `DrcSourceLineage`;
- regulatory citation ids.

The row API translates notional, market value, and cumulative P&L into the base
currency before calling the existing gross JTD, maturity, netting, and capital
chain. The original `DrcPosition` records remain in `DrcCapitalResult` for
input audit, while calculated intermediates carry base-currency amounts.

The Arrow/batch API applies the same translation to numeric arrays before the
vectorized gross JTD calculation. It does not materialize accepted row
dataclasses for converted positions.

Applied per-currency rates are recorded in `DrcCapitalResult.fx_conversions`
and run-level branch metadata. When any conversion is applied, the result
`input_hash` includes both the raw position input hash and FX conversion
lineage, preventing two runs with different rates from sharing the same result
id.

Missing rates, stale rates, rates targeting another currency, non-finite rates,
and non-positive rates fail closed with `DrcInputError`. Base-currency
positions do not require an explicit 1.0 rate.

## Consequences

This changes numerical outputs for valid multi-currency books and requires a
`frtb-drc` changelog fragment under ADR 0015, but no direct package version bump
in the feature PR.

Adapters must pass rate data explicitly. The calculation path performs no
network, file, or market-data lookup and remains deterministic from supplied
inputs.

The DRC batch path remains columnar: conversion uses one vectorized rate array
and read-only converted numeric arrays, preserving the no-row-materialisation
contract introduced for high-volume calculations.

## References

- [U.S. NPR 2.0, 91 FR 14952](https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959).
- Proposed section `__.207(a)(8)`, 91 FR 15215.
- Proposed section `__.208(h)(1)(ii)`, 91 FR 15225.
- Proposed section `__.210(a)` and `__.210(b)(1)(iii)`, 91 FR 15235-15236.
- #338.
