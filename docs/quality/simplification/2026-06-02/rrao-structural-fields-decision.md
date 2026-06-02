# RRAO structural-field and validation-duplication decision

Issue: #382

This decision follows the `frtb-rrao` simplification audit. It decides the
status of RRAO structural fields that are validated, serialized, and hashed but
do not directly drive classification or capital today, and records the
package-local validation rules that are safe candidates for future extraction.

## Decision

Keep the storage-only structural fields in the canonical RRAO input schema and
hash contract:

- `underlying_count`
- `is_path_dependent`
- `has_maturity`
- `has_strike_or_barrier`
- `has_multiple_strikes_or_barriers`
- `is_ctp_hedge`

These fields remain audit and evidence attributes, not auto-classification
inputs. They preserve upstream product facts, support fixture replay, and give
later cited classification work stable input slots. Removing them would be a
public schema and input-hash change. Using them to infer classification today
would introduce uncited auto-classification behavior, which is outside this
simplification run.

`accepted_row_dataclasses_materialized` should also remain in RRAO batch and
Arrow calculation results. For RRAO it is intentionally zero on supported fast
paths. The field is a suite performance metric that proves batch execution did
not fall back to row dataclass materialization; it is not a capital input.

## Field treatment

| Field | Current use | Decision |
| --- | --- | --- |
| `underlying_count` | Validated, serialized, hashed, and fixture-loaded. | Keep as an audit/evidence attribute. Do not use it to auto-classify CTP or optionality evidence without a cited rule change. |
| `is_path_dependent` | Validated, serialized, hashed, and fixture-loaded. | Keep as an audit/evidence attribute. Do not infer `PATH_DEPENDENT_OPTION` evidence from it. |
| `has_maturity` | Validated, serialized, hashed. | Keep as an audit/evidence attribute for upstream optionality characterization. |
| `has_strike_or_barrier` | Validated, serialized, hashed. | Keep as an audit/evidence attribute for upstream optionality characterization. |
| `has_multiple_strikes_or_barriers` | Validated, serialized, hashed. | Keep as an audit/evidence attribute for upstream optionality characterization. |
| `is_ctp_hedge` | Validated, serialized, hashed, and present in sample-book fixtures. | Keep as an audit/evidence attribute. Do not infer exclusion or capital treatment from it without cited profile support. |
| `accepted_row_dataclasses_materialized` | Always zero in current RRAO batch and Arrow paths; tests assert zero. | Keep as an intentional performance metric. Non-zero values would indicate a future fallback path and should remain visible. |

## Validation-rule extraction candidates

The following duplicated row/batch validation rules are package-local
extraction candidates. They should stay in `frtb-rrao`; none belongs in
`frtb-common` because the rules are RRAO-specific and carry regulatory
semantics.

| Rule area | Row path | Batch path | Candidate extraction |
| --- | --- | --- | --- |
| Structural optional fields | `validation._validate_optional_fields` | batch array coercion plus `_optional_int` and bool coercion | Shared scalar validators for optional non-negative int and optional bool fields, with vector adapters in `batch.py`. |
| Supervisor directive evidence | `validation._validate_evidence_requirements` | `batch._validate_evidence_requirements` | Shared rule constants and message/field helpers for supervisor-directed evidence. |
| Explicit exclusion requirements | `validation._validate_evidence_requirements` | `batch._validate_evidence_requirements` | Shared rule constants and error-message helpers for exclusion reason and evidence-id requirements. |
| Back-to-back evidence shape | `validation._validate_back_to_back_match_fields` | `batch._validate_evidence_requirements` and `batch._validate_back_to_back_match_groups` | Shared scalar validators for match group id, matched position id, and self-match rejection. |
| Back-to-back pair invariants | `validation._validate_exact_back_to_back_pair` | `batch._validate_back_to_back_match_groups` | Shared pair-invariant checks for cross-reference, evidence-id, currency, notional, and exactly-two group constraints. |
| Investment-fund linkage | `validation._validate_investment_fund_fields` | `batch._validate_investment_fund_fields` | Shared scalar rule predicates and messages, with batch retaining vectorized mask construction. |

## Implementation guidance

If this decision is implemented as code, add a package-local module such as
`frtb_rrao._validation_rules` and keep `validation.py` and `batch.py` as the
public and vectorized adapters. Do not collapse the batch path into row
dataclass materialization; doing so would defeat the zero-materialization
performance contract. Any future change that removes fields, changes payload
keys, or changes input hashes must be a separate schema/hash PR with explicit
fixture and replay updates.

## Follow-up split

No schema or hash follow-up issue is required from this decision because the
fields remain in place. A future package-local implementation issue may extract
the validation-rule helpers above once the next simplification pass targets
RRAO validation duplication specifically.
