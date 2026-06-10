# Client reference data attachment matrix

This matrix tells client integration teams where canonical input values should
come from before a capital run. It separates data the client must deliver from
rule tables owned by the library and hybrid fields where clients supply stable
keys while the library applies cited tables or run-scoped overlays.

Outputs from this suite are not final regulatory capital. U.S. NPR 2.0 content
is proposed-rule comparison material.

## Source categories

| Source | Meaning |
| --- | --- |
| CLIENT | Upstream systems must supply the value on each row or join it before input_table. |
| LIBRARY | Package rule tables or profiles resolve the value from client-supplied keys. |
| HYBRID | Client supplies keys or optional overlays; the library applies cited rules and fails closed when mandatory evidence is absent. |

For HYBRID rows, client overlays take precedence only where the package context
explicitly exposes an override map. Otherwise the package rule table remains the
source of truth. Missing mandatory overlay evidence is a validation error, not a
silent default.

## SBM

| Field / axis | Source: CLIENT \| LIBRARY \| HYBRID | Delivery mechanism | Required when | Notes / citation |
| --- | --- | --- | --- | --- |
| `sensitivity_id`, `source_row_id`, desk, legal entity | CLIENT | Arrow input_table columns or CRIF adapter output | All SBM input_tables | Stable row identity supports replay and attribution. |
| `risk_class`, `risk_measure` | CLIENT | InputTable columns | All SBM rows | Must match a supported BASEL_MAR21 path; non-Basel profiles fail closed. |
| Bucket and qualifier keys | CLIENT | `bucket`, `qualifier`, `risk_factor`, issuer or curve identifiers | All delta, vega, and curvature rows | Client owns product classification and identifier mastering before input_table. |
| Tenor / maturity / curve axis | CLIENT | `tenor`, maturity columns, or risk-class-specific axis columns | GIRR, CSR, vega, and curvature paths using tenor-sensitive rules | Library validates against package tenor sets. |
| Sensitivity amount and currency | CLIENT | `amount`, `amount_currency` or package-specific amount columns | All rows | Client ETL must apply sign convention before input_table. |
| Risk weights and correlations | LIBRARY | `frtb_sbm.reference_data` and risk-class reference modules | Supported BASEL_MAR21 rows | Basel MAR21 risk weights, correlations, and bucket tables are package-owned. |
| Equity repo and CTP decomposition evidence flags | HYBRID | Evidence columns or context flags where implemented | Paths requiring explicit evidence | Missing evidence fails closed under the package validation policy. |
| Regulatory profile | LIBRARY | `SbmCalculationContext.profile` / profile enum | Every run | BASEL_MAR21 is the supported runtime profile; U.S. NPR 2.0, EU CRR3, and PRA UK CRR comparison profiles are documented as unsupported fail-closed. |

## DRC

DRC class-specific rows must be split before batch calculation:
non-securitisation, securitisation non-CTP, and CTP.

| Field / axis | Source: CLIENT \| LIBRARY \| HYBRID | Delivery mechanism | Required when | Notes / citation |
| --- | --- | --- | --- | --- |
| `position_id`, `source_row_id`, desk, legal entity | CLIENT | DRC input_table columns | All DRC classes | Stable `position_id` is also the key for run-scoped maps. |
| `risk_class` | CLIENT | Class-specific input_table table | All DRC rows | Mixed classes in one batch fail closed. |
| Issuer, obligor, tranche, or securitisation identifier | CLIENT | `issuer_id`, `issuer_name`, `position_id`, and tranche fields | All rows | Client owns mastering; library does not source issuer records. |
| Non-securitisation bucket | HYBRID | `bucket_key` plus package validation | Non-sec rows | Client supplies a bucket key; library validates against cited Basel MAR22 / package profile tables. |
| Non-securitisation seniority | CLIENT | `seniority` | Non-sec rows | Used in LGD and netting treatment. |
| Non-securitisation credit quality | HYBRID | `credit_quality` or package profile resolution | Non-sec rows | Client may supply classification; library applies supported risk-weight table where implemented. |
| Non-securitisation LGD | HYBRID | Row field or package default by seniority/profile | Non-sec rows | Client override is accepted only through documented fields; invalid values fail closed. |
| Gross JTD inputs, notional, P&L, maturity | CLIENT | DRC input_table columns | All classes | Client signs and scales values before input_table. |
| Currency and base currency | HYBRID | Row `currency`; `DrcCalculationContext.base_currency`; `fx_rates` map | Any non-base-currency row | `fx_rates` keys are source currency codes. Missing `source_currency -> base_currency` rate or missing lineage raises `DrcInputError`. |
| `securitisation_non_ctp_risk_weights` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id` | Securitisation non-CTP rows | Mandatory for each position when typed evidence is not supplied for a supported profile; unused keys and missing keys fail closed. |
| `securitisation_non_ctp_risk_weight_evidence` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id`, optionally built from `DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS` through `build_drc_securitisation_non_ctp_risk_weight_evidence_from_arrow` | Securitisation non-CTP rows | Evidence records carry source profile, source table/method, source id, lineage, citation ids, and validation flags. Missing, stale, uncited, future-dated, profile-mismatched, or wrong-class evidence fails closed. |
| `securitisation_non_ctp_fair_value_cap_evidence` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id`, optionally built from `DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS` through `build_drc_fair_value_cap_evidence_from_arrow` | Securitisation non-CTP rows where fair-value cap applies | Profile must allow the cap; incomplete, stale, future-dated, uncited, or unused evidence fails closed. |
| `securitisation_non_ctp_offset_groups` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id` to offset group | Securitisation non-CTP netting | Client supplies decomposition/replication grouping evidence. Missing explicit group can fall back only to supported row evidence; unsupported offsets fail closed. |
| `ctp_risk_weights` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id` | CTP rows | Mandatory for every CTP position when typed evidence is not supplied for a supported profile; missing or unused keys fail closed. |
| `ctp_risk_weight_evidence` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id`, optionally built from `DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS` through `build_drc_ctp_risk_weight_evidence_from_arrow` | CTP rows | Evidence must include source, lineage, and citation ids. Missing, stale, uncited, future-dated, profile-mismatched, or wrong-class evidence fails closed. |
| `ctp_offset_groups` | HYBRID | `DrcCalculationContext` mapping keyed by `position_id` | CTP offset grouping | Optional only where package rules can derive a supported group; unsupported decomposition evidence fails closed. |

Key rule: DRC run-scoped maps are keyed by stable `position_id` unless the
specific context type documents a narrower key. The package validates missing
and unused map entries to prevent accidental stale attachments. Arrow evidence
handoffs are adapter-layer conveniences for building those same maps; they do
not derive internal banking-book risk weights and do not bypass context
validation.

## RRAO

| Field / axis | Source: CLIENT \| LIBRARY \| HYBRID | Delivery mechanism | Required when | Notes / citation |
| --- | --- | --- | --- | --- |
| `position_id`, `source_row_id`, desk, legal entity | CLIENT | RRAO input_table columns | All RRAO rows | Required for replay and allocation. |
| `gross_effective_notional`, `currency` | CLIENT | RRAO input_table columns | All RRAO rows | Notional must be finite and non-negative after client sign normalization. |
| `evidence_type`, `evidence_label` | CLIENT | RRAO input_table columns | All rows | Evidence type drives classification and exclusion validation. |
| Classification rule tables | LIBRARY | `frtb_rrao.reference_data` and profile helpers | All supported profiles | Basel MAR23 residual-risk classification and comparison profile logic live in package rules. |
| `classification_hint` | HYBRID | Optional input_table column | When client pre-classifies or has supervisor-directed classification | Library validates hints and rejects unsupported classifications. |
| Explicit exclusion fields | CLIENT | `exclusion_reason`, `exclusion_evidence_id` | Rows claiming exclusion | Exclusion reason requires explicit exclusion evidence; no silent row drops. |
| Back-to-back match evidence | CLIENT | Flat columns: `back_to_back_match_group_id`, `back_to_back_matched_position_id` | Exact third-party back-to-back exclusions | Nested JSON blobs are rejected through `unsupported_nested_payload`. |
| Supervisor directive evidence | CLIENT | `supervisor_directive_id` | Supervisor-directed classification or evidence type | Missing directive id fails closed. |
| Investment-fund descriptor fields | CLIENT | Flat columns such as `investment_fund_id`, `investment_fund_section_205_method`, `investment_fund_included_exposure_type`, evidence ids, ratios, and look-through flags | Investment-fund exposures | Descriptor must be flattened before input_table; this aligns with [RRAO Arrow batch triage](performance/frtb-rrao-arrow-batch-triage.md). |
| Citation ids and lineage | CLIENT | `citations`, `lineage_source_system`, `lineage_source_file`, `lineage_source_row_id` | Audit-ready runs | Lineage is required for canonical validation. |

## CVA

| Field / axis | Source: CLIENT \| LIBRARY \| HYBRID | Delivery mechanism | Required when | Notes / citation |
| --- | --- | --- | --- | --- |
| Counterparty identity, desk, legal entity | CLIENT | `CVA_COUNTERPARTY_ARROW_COLUMN_SPECS` | All CVA methods | Client owns counterparty mastering. |
| Counterparty sector, credit quality, region | HYBRID | Counterparty input_table columns plus package validation | BA-CVA and SA-CVA profile calculations | Client supplies classification keys; package validates supported values and applies cited weights. |
| Netting-set EAD, maturity, discount factor, currency | CLIENT | `CVA_NETTING_SET_ARROW_COLUMN_SPECS` | BA-CVA and mixed-method runs | EAD is non-negative after sign normalization; discount factor must be positive. |
| `uses_imm_ead`, carve-out flags | CLIENT | Netting-set input_table columns and `CvaCalculationContext` | BA-CVA / SA-CVA carve-out logic | Invalid references fail closed. |
| Hedge type, reference relation, eligibility | HYBRID | `CVA_HEDGE_ARROW_COLUMN_SPECS` | Hedge recognition | Client supplies hedge metadata and evidence ids; package validates eligibility and unsupported hedge recognition paths. |
| SA-CVA sensitivity risk class, measure, bucket, factor, tenor | CLIENT | `SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS` | SA-CVA runs | GIRR delta requires tenor; vega requires volatility input. |
| Qualified-index metadata | HYBRID | SA-CVA sensitivity columns such as `index_max_sector_weight`, `index_remap_bucket_id`, `index_dominant_sector` | Index sensitivities and hedges | Client supplies index evidence; package applies qualified-index remapping where supported. |
| `m_cva`, method, materiality election | HYBRID | `CvaCalculationContext` | Every CVA run | Materiality-threshold alternative is unsupported and fails closed. |

## IMA

| Field / axis | Source: CLIENT \| LIBRARY \| HYBRID | Delivery mechanism | Required when | Notes / citation |
| --- | --- | --- | --- | --- |
| Scenario P&L cube | CLIENT | Dense NumPy `.npz` arrays / `ScenarioCube` | ES, LHA, IMCC, and NMRF capital paths | This is not reference data and must not be put into Arrow input_table for capital kernels. |
| Scenario metadata | CLIENT | `IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS` | Scenario cube lineage and replay | Arrow metadata rows describe scenario ids, dates, liquidity horizons, and lineage. |
| RFET observations | CLIENT | `IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS` | RFET assessment | Client supplies real-price observation evidence; package assesses eligibility. |
| Capital-run input manifest rows | CLIENT | `IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS` | Fixture and delivery-pack replay | Names artifacts, source systems, checksums, record counts, and vector counts. |
| Calendars and liquidity-horizon mappings | HYBRID | Package calendar/mapping helpers plus client governance inputs | IMA validation and LHA | Client owns governance evidence; library applies implemented mapping rules. |
| Stress period, NMRF valuation artifacts, PLA/backtesting vectors | CLIENT | Dense arrays and package fixture artifacts | IMA capital assembly | Pricing, NMRF revaluation, and scenario generation remain upstream. |

## Manifest attachment naming

`CapitalRunManifest` names reference attachments explicitly so a validator can
match them to component input_tables:

| Logical attachment | Intended content | Hash expectation |
| --- | --- | --- |
| `drc.fx_rates` | FX rates with source and target currency, source id, lineage, and citation ids | Stable hash of rates used for the run. |
| `drc.securitisation_non_ctp.risk_weights` | Position-id keyed raw risk weights where supported | Stable hash included in DRC context input hash. |
| `drc.securitisation_non_ctp.risk_weight_evidence` | Arrow or mapping-backed typed securitisation non-CTP risk-weight evidence | Stable hash included in DRC context input hash. |
| `drc.securitisation_non_ctp.fair_value_cap` | Arrow or mapping-backed position-id keyed fair-value cap evidence | Stable hash included when cap evidence applies. |
| `drc.securitisation_non_ctp.offset_groups` | Position-id keyed decomposition or replication groups | Stable hash of groups used for netting. |
| `drc.ctp.risk_weights` | Position-id keyed raw CTP risk weights where supported | Stable hash included in CTP context input hash. |
| `drc.ctp.risk_weight_evidence` | Arrow or mapping-backed typed CTP risk-weight evidence | Stable hash included in CTP context input hash. |
| `drc.ctp.offset_groups` | Position-id keyed CTP offset groups | Stable hash of groups used for CTP netting. |
| `cva.counterparty_reference` | Optional client counterparty sector, credit-quality, and region attachment | Stable hash if supplied outside the counterparty table. |
| `rrao.classification_evidence` | Optional evidence catalog referenced by flat RRAO row columns | Stable hash if supplied outside the positions table. |
| `ima.artifact_manifest` | IMA input-manifest table naming NPZ, CSV, and evidence artifacts | Stable hash of artifact metadata and checksums. |

File-backed clients can use `scripts/validate_client_input_table.py` before
constructing a runtime manifest. In-memory clients should supply Arrow tables
and let `validate_capital_run_manifest` compute source and input_table hashes.
