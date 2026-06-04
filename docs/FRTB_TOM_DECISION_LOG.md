# FRTB Target Operating Model — Decision Log

Companion to the [FRTB Target Operating Model](FRTB_TARGET_OPERATING_MODEL.md).
The main document reads as a narrative design; this log records the underlying
decisions, the open questions, and the regime-identifier reference, so the design
choices remain traceable without cluttering the narrative.

Decisions were taken in three review rounds. Each row records the choice and its
principal consequence for the operating model.

---

## Round 1 — foundations

| # | Area | Decision | Consequence |
| --- | --- | --- | --- |
| 1 | Jurisdiction | US (NPR) | US regime profiles; FFIEC-style return; US DRC bucket taxonomy authoritative |
| 2 | IMA scope | IMA + SA from day one | PLA, backtesting, NMRF/SES, stress periods, and desk eligibility are all in the go-live critical path |
| 3 | Run cadence | Daily T+1 batch | One official run on prior close; any intraday figure is an estimate only |
| 4 | Org topology | Centralised Risk Analytics | A single team operates the run and owns reconciliation and attribution suite-wide |
| 5 | Risk engine | In-house | Tier 1 Arrow/Parquet contract; internal Quant owns pricing and sensitivity methodology |
| 6 | Deployment | On-premise | Internal grid and scheduler, on-prem storage co-located with the risk engine |
| 7 | Finance seam | Controlled file handover | Risk Analytics produces a reviewed, signed-off extract that Finance ingests |
| 8 | MRM gating | Conditional use with findings | Components may go live with documented findings and remediation timelines tracked to closure |
| 9 | Reporting line | 2LOD under the CRO | Capital production is independent of the front office |
| 10 | Change management | Quarterly release train | Methodology and regime changes are bundled quarterly with a parallel run; emergency patches are the exception |

## Round 2 — operational detail

| # | Area | Decision | Consequence |
| --- | --- | --- | --- |
| 11 | RFET thresholds | Configurable per regime | Observation count, maximum gap, window, and bucketing are profile parameters; US, Basel, and conservative variants coexist |
| 12 | Observation sourcing | Internal-primary | The internal observability database is the system of record; vendor pools fill the gaps |
| 13 | Desk eligibility | Market Risk (2LOD) decides directly | No separate board; eligibility is called straight off the library's traffic-light |
| 14 | Run SLA / DR | Best-effort, no fallback | Correctness over cadence; a late feed slips the run rather than substituting stale numbers |
| 15 | Break / sign-off gate | Tiered RAG per component | Green passes automatically, amber needs a Risk Analytics note, red blocks the Finance handover until Market Risk approves |
| 16 | Parallel run | One month | Each release-train change runs a month against the incumbent before cutover |
| 17 | Go-live sequencing | SA first, then IMA per desk | The model is designed for full IMA + SA; capital-of-record rolls out SA first, with IMA switched on as evidence matures |
| 18 | Retention | 7-year WORM, full lineage | Every capital-of-record run is write-once for seven years with input lineage and hashes |
| 19 | Access / SoD | Role-based, environment-gated | Production config is locked to the release train; only the scheduler triggers official runs; humans are read-only in production |
| 20 | Conditional-use cap | Time-boxed | Conditional use is granted for a fixed window; unclosed findings revert the component to a standardised fallback |

## Round 3 — scope, governance, and data ownership

| # | Area | Decision | Consequence |
| --- | --- | --- | --- |
| 21 | Capital stack | Dual-stack, larger binds | Orchestration computes both the expanded and the standardised total RWA; the larger is capital-of-record |
| 22 | Desk boundary | Inherit management desks 1:1 | Regulatory desks mirror management/booking desks, with a MAR12 compliance caveat to confirm |
| 23 | Reference-data governance | Quant owns, via the release train | Bucket, weight, and correlation tables are treated as model parameters and change through the release train |
| 24 | Input data quality | Source-system ownership | Each feed certifies its own data quality; Risk Analytics monitors; the library's fail-closed behaviour is the backstop |
| 25 | Limits linkage | Capital is measurement-only | FRTB capital is reported but does not bind desk limits, which run off separate market-risk measures |
| 26 | Governance forum | Dedicated FRTB Steering Committee | Risk, Quant, Finance, IT, and MRM own methodology and outcomes, escalating to the Model Risk and Capital committees |
| 27 | CVA data ownership | Risk Analytics consolidates | Risk Analytics sources counterparty exposure and eligible hedges and curates the CVA inputs |
| 28 | RFET vendor pool | Govern the slot, decide later | The third-party governance requirements are defined now; the specific pool is selected in procurement |
| 29 | Reduced data set | Library-driven selection | The library selects the reduced set each run to meet the captured-share floor; Quant reviews |
| 30 | RFET interim stance | Basel MAR31 default | The US profile is seeded with Basel MAR31 thresholds pending confirmation of the exact US figures |

---

## Regime-profile identifiers

"US NPR" is the prose shorthand used in the main document. The implemented profile
enum identifiers differ by package:

| Package(s) | US identifier | EU / UK / Basel identifiers |
| --- | --- | --- |
| `frtb-ima` | `RegulatoryRegime.FED_NPR_2_0` | `ECB_CRR3`, `PRA_UK_CRR` |
| `frtb-sbm`, `frtb-drc` | `US_NPR_2_0` | `BASEL_MAR21` |
| `frtb-cva` | `CvaRegulatoryProfile.US_NPR20_VB` | `BASEL_MAR50_2020`, `EU_CRR3_CVA`, `UK_PRA_CVA` |

---

## Open-items register

### Resolved during the review rounds

| Item | Question | Resolution |
| --- | --- | --- |
| O1 | T+1 run SLA and recovery path | Decision 14 — best-effort, no fallback |
| O2 | Desk IMA-eligibility governance | Decision 13 — Market Risk (2LOD) decides directly |
| O3 | Break / sign-off thresholds | Decision 15 — tiered RAG per component |
| O4 | Parallel-run rules | Decision 16 — one month parallel |
| O5 | Go-live sequencing | Decision 17 — SA first, then IMA per desk |
| O6 | Retention and immutability | Decision 18 — 7-year WORM |
| O7 | Access and segregation of duties | Decision 19 — role-based, environment-gated |
| O8 | Conditional-use cap | Decision 20 — time-boxed, reverts to SA |
| O9 | US RFET and NMRF specifics | Decision 30 — Basel MAR31 interim (exact figures: see O9-residual) |
| O10 | RFET observation-data sourcing | Decisions 12 and 28 — internal-primary, vendor slot governed |
| Capital stack | Which RWA stack binds | Decision 21 — larger of expanded vs standardised |
| Desk boundary | Definition and re-approval | Decision 22 — inherit management desks (caveat: O12) |
| Reference data | Rule-table ownership | Decision 23 — Quant, release train |
| Input data quality | Pre-run gate ownership | Decision 24 — source-system certificates |
| Limits | Capital vs limits | Decision 25 — measurement-only |
| Governance | Committee map | Decision 26 — FRTB Steering Committee |
| CVA data | Exposure / hedge provenance | Decision 27 — Risk Analytics consolidates |
| Reduced data set | Selection and refresh | Decision 29 — library-driven |

### Still open

| Item | Description |
| --- | --- |
| O9-residual | Pin the exact US RFET thresholds and the Type A/B idiosyncratic-NMRF criteria against the final-rule text, replacing the Basel MAR31 interim. A regulatory-sourcing task for Quant, regulatory traceability, and MRM. |
| O11 | Encode the transitional output-floor percentage and phase-in (toward 72.5%) for the EU and UK regimes, where the floor binds on the expanded stack as a percentage of the standardised stack. The US needs no separate schedule — its dual-stack greater-of test is the floor. |
| O12 | Confirm that the inherited management-desk structure meets the MAR12 qualitative desk-definition and granularity standards, and define the remediation path if it does not. |
| O13 | Detail the internal observation-capture build, the vendor-gap reconciliation, and the CCR/SA-CCR to CVA exposure interface. |

### Not yet modelled

Prudent valuation and IPV interaction, BCBS 239 data-aggregation lineage
attestation, and a full disaster-recovery / business-continuity plan beyond the
run SLA are acknowledged gaps not yet in the decision register.
