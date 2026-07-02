# 51. RFET observation and vendor mapping evidence boundary

Date: 2026-07-01

## Status

Proposed

## Context

[ADR 0049](0049-result-evidence-and-market-data-platform-boundary.md) defines
the boundary between run-scoped regulatory evidence and enterprise
market/scenario-data platforms. [ADR 0050](0050-risk-factor-identity-and-package-projection-boundary.md)
defines risk-factor identity and package projection boundaries.

RFET needs a narrower decision because real-price observation evidence is not
just a generic time series. Observation sources often identify risk factors
with vendor quote IDs, instrument IDs, curve labels, venue identifiers,
front-office labels, internal risk labels, or ad hoc source-system keys. Those
identifiers must be mapped to run-scoped `risk_factor_id` values and then to
IMA-owned RFET projections before modellability can be assessed.

The repository already has IMA RFET evidence and risk-factor master mapping
code. The next risk is architectural drift: result-store or Navigator code
could start resolving ambiguous source labels, or `frtb-capital` could grow
into a vendor observation collection and data-quality platform.

This ADR defines what RFET observation and mapping evidence the suite may own,
and what remains external.

## Decision

`frtb-ima` owns RFET regulatory interpretation for committed runs:

- RFET observation projection into IMA inputs;
- quantitative and qualitative RFET assessment;
- modellability/NMRF status;
- observation-window evidence;
- package-local citations and diagnostics.

`frtb-result-store` may persist and expose the exact RFET observation and
mapping evidence consumed by a committed IMA run. It owns availability,
referential checks, paging, lineage, and diagnostics transport. It must not
invent mappings or decide modellability.

External vendor, market-data, reference-data, or observation platforms own:

- real-price observation collection;
- vendor quote/instrument/curve identifier lifecycle;
- golden-source mapping governance;
- cross-asset source normalization;
- observation deduplication policy outside the committed run;
- live observability dashboards and operational remediation workflows.

The boundary rule is:

```text
The suite records the RFET observation and mapping evidence used by a run.
It does not operate the upstream observation collection or mapping platform.
```

## Scope owned by `frtb-capital`

### 1. Run-scoped RFET observation evidence

The suite may persist or reference the observation rows consumed by an IMA run.
When RFET observation evidence is persisted directly, each row must include:

- `run_id`;
- source system;
- source row id;
- observation date;
- observed value or observation marker;
- source identifier, such as quote id, instrument id, curve label, or internal
  source key;
- IMA `risk_factor_name` or package projection key;
- mapping status;
- observation status;
- reason code for excluded, rejected, or unresolved rows;
- source hash or artifact hash.

Rows may also include mapped `risk_factor_id`, `risk_factor_set_id`, mapping
version, and mapping hash when the run has a declared risk-factor catalog.

This evidence can use a generic time-series artifact for storage, but RFET
behavior requires an RFET semantic profile with IMA ownership, required fields,
validation rules, and citations.

Existing IMA RFET paths keyed by `risk_factor_name` remain valid package
projection inputs. Adding `risk_factor_id` and row-level mapping diagnostics is
additive hardening, not a prerequisite for the current RFET assessment code.

### 2. Vendor/internal source mapping evidence

Vendor and internal source identifiers are not canonical `risk_factor_id`
values. The suite may persist the exact mapping evidence used by a run:

- source system;
- source identifier type;
- source identifier value;
- source row id;
- vendor quote, instrument, curve, tenor, venue, or label fields where
  available;
- mapped `risk_factor_id`;
- mapped IMA `risk_factor_name`;
- mapping version;
- mapping hash;
- effective date;
- mapping status;
- observation status;
- reason code and diagnostic message.

Allowed mapping statuses are:

| Status | Meaning |
| --- | --- |
| `MAPPED` | Source identifier resolved to one run-scoped `risk_factor_id` and IMA projection |
| `UNMAPPED` | Source identifier did not resolve to a run-scoped risk factor |
| `AMBIGUOUS` | Source identifier matched multiple candidate risk factors or projections |

Allowed observation statuses are:

| Status | Meaning |
| --- | --- |
| `INCLUDED` | Row is accepted into the RFET observation assessment input |
| `EXCLUDED` | Row is mapped or understood but intentionally excluded by package or external policy |
| `REJECTED` | Row failed required shape, date, value, lineage, or profile validation |

Mapping status describes source-to-risk-factor resolution. Observation status
describes whether the row enters the RFET assessment input. A row can be
`MAPPED` and `EXCLUDED`. IMA owns any downstream RFET pass/fail, modellability,
or NMRF classification.

RFET implementations should distinguish two outputs:

- accepted observation batches used by IMA assessment code;
- diagnostic evidence containing rejected, excluded, unmapped, or ambiguous
  source rows needed for audit.

The diagnostic evidence may be stored separately from the accepted batch as long
as the committed run preserves both the assessment input and the rejected or
unresolved rows relevant to the result.

### 3. IMA RFET semantic profile

An RFET observation semantic profile must declare:

- owner package: `frtb-ima`;
- storage artifact schema and artifact type;
- required identifier fields;
- required time axis and ordering key;
- observation-window policy inputs;
- source mapping status rules;
- inclusion/exclusion rules;
- RFET assessment output fields;
- regulatory citations used by IMA validation;
- Navigator display behavior.

The profile must also declare how source rows map to:

- `risk_factor_id`;
- optional `risk_factor_set_id`;
- IMA `risk_factor_name`;
- IMA risk class;
- IMA liquidity horizon;
- RFET observation batch rows.

### 4. Result-store responsibilities

`frtb-result-store` may:

- validate required RFET observation and mapping fields before commit;
- validate that mapped `risk_factor_id` values resolve to the run-scoped
  risk-factor catalog when one is declared;
- store unavailable refs for no-data or unsupported RFET evidence;
- expose paged observation and mapping evidence to the Navigator;
- expose mapping status counts and diagnostics;
- preserve source hashes, mapping hashes, source row ids, and artifact ids.

`frtb-result-store` must not:

- map vendor/source identifiers to risk factors;
- choose between ambiguous candidates;
- infer liquidity horizons;
- infer RFET pass/fail status from raw observations;
- convert unresolved rows into zeros or silently drop them.

### 5. Navigator responsibilities

The FRTB Navigator may display:

- RFET observation rows;
- source identifiers and mapped risk-factor IDs;
- mapping statuses and diagnostics;
- IMA-owned modellability/NMRF status;
- observation-window summaries and counts when supplied by IMA/result-store
  evidence.

The Navigator must not:

- resolve `UNMAPPED` or `AMBIGUOUS` rows by matching labels;
- infer risk-factor IDs from vendor quote IDs, tenor text, currency codes, or
  source row ids;
- decide modellability from raw observation counts;
- hide rejected or ambiguous mappings when they affect the selected result;
- convert absent evidence into RFET counts or pass/fail conclusions.

The Navigator may display zero counts only when those counts are supplied by
IMA-owned assessment evidence.

## Scope explicitly outside `frtb-capital`

The following remain outside this repository:

- vendor real-price feed ingestion;
- RFQ, trade, quote, and venue capture workflows;
- vendor symbology normalization;
- market-data licensing and permission management;
- enterprise source-to-risk-factor mapping approval workflow;
- live RFET operations dashboards;
- manual remediation workflows for unresolved mappings;
- long-history observation storage outside committed run evidence.

External platforms may produce mapping snapshots, observation extracts,
validation reports, object-store URIs, hashes, and source-row identifiers. The
suite records what a committed run consumed.

The suite may store vendor/source identifiers for provenance. It does not assert
license entitlement, redistribution rights, or permissioning decisions for those
sources.

## Design rules

### Rule 1: source identifiers are not canonical risk-factor IDs

Vendor quote IDs, instrument IDs, curve labels, venue labels, source row ids,
and internal FO/risk labels must not be treated as `risk_factor_id` values.
They require explicit mapping evidence.

### Rule 2: mapping is evidence, not silent preprocessing

Every source row used for RFET should be traceable to a mapping status. If a
row is excluded, rejected, unmapped, or ambiguous, the reason must be preserved
when that row is relevant to the committed run.

Observation acceptance is a separate evidence axis. Rows used for RFET should
also be traceable to `INCLUDED`, `EXCLUDED`, or `REJECTED` observation status.

### Rule 3: unresolved required mappings fail package acceptance

When an RFET semantic profile requires mapped observations, unresolved required
mappings must fail IMA package acceptance or produce an explicit unsupported/no
data diagnostic. They must not silently disappear.

### Rule 4: RFET status is IMA-owned

IMA owns RFET quantitative and qualitative interpretation. Result-store and UI
code may transport and display IMA-owned statuses, but must not compute them.

### Rule 5: source and mapping hashes are part of replay

RFET evidence should preserve source hashes and mapping hashes. A different
source extract or mapping version should produce a different committed evidence
reference, artifact hash, or run input hash.

### Rule 6: mappings are effective-dated or snapshot-scoped

Mapping evidence must include an effective date, snapshot timestamp, or mapping
version. Replaying a committed run must not depend on the current state of an
external mapping service.

### Rule 7: duplicate outcomes are evidence

Upstream duplicate-detection and deduplication policy is external. When
duplicate source rows affect a committed RFET result, the run evidence should
preserve which rows were included, excluded, or rejected and why.

## Examples

### In scope

- Persisting an RFET observation artifact with source quote id, source row id,
  mapped `risk_factor_id`, IMA `risk_factor_name`, observation date, and
  mapping status.
- Persisting mapping diagnostics showing that three source rows were
  `AMBIGUOUS` and excluded from RFET assessment.
- Exposing IMA-owned modellability status and observation-window counts through
  result-store APIs.
- Displaying mapping lineage and unresolved rows in the Navigator.
- Replaying a run from the same observation extract hash and mapping hash.

### Out of scope

- Connecting directly to Bloomberg, Refinitiv, trade capture, RFQ, or pricing
  systems.
- Building a vendor symbology normalization platform.
- Letting the UI resolve ambiguous RFET rows by matching labels.
- Letting result-store compute RFET pass/fail from raw observation rows.
- Maintaining a live RFET remediation workflow in this repo.

## Enforcement

| Rule | Enforcement |
| --- | --- |
| Source identifiers are not canonical risk-factor IDs | RFET mapping tests and review |
| Mapping statuses are preserved | IMA adapter tests and result-store artifact tests |
| Observation statuses are preserved separately from mapping status | IMA adapter tests and result-store artifact tests |
| Unresolved required mappings do not silently pass | IMA validation tests |
| RFET status is IMA-owned | Package-boundary review and no UI/result-store RFET classifiers |
| Source/mapping hashes are replay evidence | Artifact schema tests and fixture checks |
| Navigator does not resolve ambiguous rows | Frontend tests and metadata-contract review |

Changes that add RFET observation behavior without source lineage, mapping
status, owner package, and replay hashes should be rejected or scoped behind a
new ADR.

## Consequences

**Positive:**

- RFET evidence becomes auditable from source row to risk-factor projection to
  modellability status.
- Vendor/internal source identifiers cannot leak into the suite as accidental
  canonical IDs.
- Result-store and Navigator can expose unresolved mapping problems without
  owning remediation workflows.
- IMA keeps regulatory RFET interpretation and citations.

**Negative:**

- RFET fixture and ingestion work needs explicit mapping diagnostics, not just
  observation rows.
- A useful production RFET workflow still requires an external observation and
  mapping platform.
- More artifact rows may be persisted to preserve rejected, ambiguous, or
  excluded evidence.

**Risks to guard against:**

- Treating vendor quote IDs or source labels as stable risk-factor IDs.
- Dropping ambiguous or rejected rows before audit evidence is written.
- Recomputing modellability in the UI for convenience.
- Depending on current external mapping-service state to explain an old run.
- Turning result-store into a live RFET operations platform.

## Follow-up work

- Define an RFET observation semantic profile over the existing time-series
  artifact family.
- Define an RFET mapping-diagnostics artifact or extend the RFET profile with
  explicit mapping status rows.
- Split RFET mapping status and observation status in fixture and schema work.
- Link IMA risk-factor master mapping outputs to `risk_factor_id` and
  `RiskFactorSetId` from ADR 0050.
- Add fixture examples for `MAPPED`, `UNMAPPED`, `AMBIGUOUS`, `EXCLUDED`, and
  `REJECTED` RFET source rows.
- Add result-store APIs or catalog fields for RFET mapping status counts.
- Update the FRTB Navigator metadata contract to show RFET mapping
  diagnostics without client-side remediation.

## References

- [ADR 0012](0012-capital-impact-attribution.md): attribution-ready audit and
  branch metadata.
- [ADR 0023](0023-arrow-tabular-handoff-boundary.md): Arrow tabular handoff
  boundary.
- [ADR 0049](0049-result-evidence-and-market-data-platform-boundary.md): result
  evidence and market data platform boundary.
- [ADR 0050](0050-risk-factor-identity-and-package-projection-boundary.md): risk
  factor identity and package projection boundary.
- [`docs/modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md`](../modules/frtb-result-store/FRTB_NAVIGATOR_METADATA_CONTRACT.md):
  FRTB Navigator metadata read-model contract.
- #1072: time-series, shocks, and surface metadata architecture.
