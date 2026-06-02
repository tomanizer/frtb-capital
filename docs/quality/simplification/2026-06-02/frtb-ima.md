# frtb-ima simplification audit

## Scope

`frtb-ima` owns model-eligible desk capital. It must not take on SBM, DRC,
RRAO, CVA, SA composition, or firm aggregation responsibilities.

## Hotspot map

| Module | Lines | Notes |
| --- | ---: | --- |
| `rfet_evidence.py` | 959 | RFET evidence assessment and batch mechanics. |
| `stress_periods.py` | 760 | Stress-period selection and audit output. |
| `backtesting.py` | 757 | Backtesting traces and validation. |
| `nmrf.py` | 743 | NMRF classification and SES logic. |
| `arrow_handoff.py` | 688 | Arrow conversion boundary. |
| `capital_run_fixture.py` | 615 | Synthetic fixture and file-hash support. |
| `nmrf_valuation_run.py` | 627 | NMRF valuation artifact validation. |
| `nmrf_method_selection.py` | 550 | NMRF method-selection policy. |
| `pla.py` | 538 | PLA metrics and diagnostics. |
| `audit.py` | 502 | Audit records and hashes. |

## Duplicated code

- `_as_finite_1d_array` appears in `backtesting.py`, `pla.py`, and
  `nmrf_method_selection.py`.
- `_readonly_string_array`, `_readonly_date_array`, `_date_from_datetime64`,
  and `_validate_equal_lengths` are repeated between `rfet_evidence.py` and
  `scenario.py`.
- `_empty_mapping` and `_freeze_mapping` appear in audit, valuation-run, stress,
  and data-contract modules.
- `_validate_observation_dates` has parallel implementations in backtesting and
  PLA flows.
- Hashing is package-local through `audit_inputs.compute_inputs_hash`, regime
  policy hashes, and fixture `_sha256`; this overlaps with suite-level stable
  hashing patterns.

## Dead or storage-only code

- No obvious dead runtime code was identified. The many `as_dict` methods are
  repetitive but serve audit serialization.
- `frtb_ima.regimes.UnsupportedRegulatoryFeatureError` is package-local while
  `frtb-common` exposes the same concept. This may be intentional API history,
  but it is a compatibility review candidate.

## `frtb-common` candidates

- Stable JSON hashing could share a common helper, but IMA's
  `compute_inputs_hash` also handles bytes and NumPy arrays specially. Keep that
  richer behavior local unless a common helper explicitly supports array/bytes
  digests.
- Arrow object/date/string conversion helpers may fit common handoff mechanics
  if their default/null behavior matches the other packages.

## Package-local factoring candidates

- Add `frtb_ima._array_utils` for finite 1D arrays and readonly string/date
  arrays.
- Add `frtb_ima._mapping_utils` for frozen metadata mappings.
- Add a package-local observation-window validation helper shared by PLA and
  backtesting.
- Consider a light serialization mixin only if it reduces the `as_dict` surface
  without hiding audit fields.

## Over-complexity

- `assess_rfet_evidence` remains a high-value split candidate from
  `docs/quality/REFACTOR_HOTSPOTS.md`: separate qualitative gates from
  quantitative evidence windows.
- Backtesting and PLA share observation-date mechanics but should keep their
  regulatory metric logic visible.
- NMRF valuation and method-selection logic is domain-specific; local helper
  extraction is safer than commonization.

## What must not move

Do not move scenario-vector granularity, liquidity-horizon adjustment logic,
RFET/NMRF classification, PLA/backtesting thresholds, policy profile semantics,
or model-eligibility handoff logic to `frtb-common`.

## Recommended sequence

1. Extract local array/date/mapping helpers.
2. Align IMA hash helpers with a future common stable-hash function where safe,
   while retaining bytes/NumPy digest behavior locally.
3. Split RFET evidence gates into named audit stages with existing tests
   unchanged.
4. Review the package-local unsupported-feature exception for compatibility with
   `frtb-common`.

## Validation required

- IMA package tests, especially RFET, PLA, backtesting, NMRF valuation, scenario
  metadata, and audit hash tests.
- `make quality-control` for boundary and maturity checks.

