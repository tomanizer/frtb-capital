# FRTB Target Operating Model (TOM) — Draft v0.4

> **Status:** Fourth draft. Incorporates **20 stakeholder decisions** across two
> rounds (see §0). Highlights: corrected **IMA evidence provenance** (RFET / NMRF
> / PLA — §4.4) with an **internal-primary** observation-sourcing model and
> **per-regime configurable** RFET thresholds; a plain-language responsibility
> matrix (§3, no RACI); a new **Market/Risk Data** function; and resolved
> operational rules for run SLA, break gating, parallel-run, retention, access
> control, and conditional-use limits. This document describes a *target* operating model for
> running FRTB market-risk capital using the `frtb-capital` library as the
> calculation engine. It is an organisational / functional / technical design
> artifact, **not** a regulatory submission. The library itself remains a
> prototype: outputs are not final regulatory capital and require independent
> model validation and supervisory approval before production use.

---

## 0. Confirmed design decisions (round 1)

These ten decisions are baked into the model below. Anything not yet decided is
flagged inline as **[OPEN]**.

| # | Decision area | Choice | Primary impact |
| --- | --- | --- | --- |
| 1 | **Jurisdiction** | **US (NPR)** | `FED_NPR_2_0` (frtb-ima) / `US_NPR_2_0` (SA & CVA) regime profiles; FFIEC-style return; US DRC bucket taxonomy (ADRs 0024–0028) authoritative |
| 2 | **IMA scope** | **IMA + SA from day one** | PLA, backtesting, NMRF/SES, stress periods, desk eligibility all in the go-live critical path |
| 3 | **Run cadence** | **Daily T+1 batch** | One official run on prior close; intraday is estimate-only |
| 4 | **Org topology** | **Centralised Risk Analytics** | Single team operates the run, owns reconciliation & attribution suite-wide |
| 5 | **Risk engine** | **In-house** | Tier 1 Arrow/Parquet contract; internal Quant owns pricing/sensitivity methodology |
| 6 | **Deployment** | **On-premise** | Internal grid/scheduler, on-prem storage co-located with risk engine |
| 7 | **Finance seam** | **Controlled file handover** | Risk Analytics produces a reviewed, signed-off extract; Finance ingests it |
| 8 | **MRM gating** | **Conditional use with findings** | Components go live with documented findings + remediation timelines tracked to closure |
| 9 | **Reporting line** | **2LOD under the CRO** | Capital production is independent of the front office |
| 10 | **Change mgmt** | **Scheduled release train (quarterly)** | Methodology/regime changes bundled quarterly with parallel-run; emergency patches exception-only |

### Round-2 decisions (operational detail)

| # | Decision area | Choice | Primary impact |
| --- | --- | --- | --- |
| 11 | **RFET thresholds** | **Configurable per regime** | Obs count, max gap, window, bucketing are `FED_NPR_2_0` (IMA) profile parameters; US/Basel/conservative variants coexist |
| 12 | **Observation sourcing** | **Internal-primary** | Internal observability DB is system-of-record for real price observations; vendor pools fill gaps |
| 13 | **Desk eligibility** | **Market Risk (2LOD) decides directly** | No separate board; eligibility called straight off the library traffic-light |
| 14 | **Run SLA / DR** | **Best-effort, no fallback** | Correctness over cadence; a late feed slips the run rather than substituting stale numbers |
| 15 | **Break / sign-off gate** | **Tiered RAG per component** | Green auto-pass, amber = Risk Analytics note, red blocks the Finance handover until Market Risk approves |
| 16 | **Parallel run** | **1 month** | Each release-train change runs one month vs incumbent before cutover |
| 17 | **Go-live sequencing** | **SA first, then IMA per desk** | TOM *designed* for full IMA+SA (decision 2); *capital-of-record* rolls out SA first, IMA switched on as evidence matures |
| 18 | **Retention** | **7-year WORM, full lineage** | Every capital-of-record run write-once for 7 years with input lineage + hashes |
| 19 | **Access / SoD** | **Role-based, environment-gated** | Prod config locked to release train; only the IT scheduler triggers official prod runs; humans read-only in prod |
| 20 | **Conditional-use cap** | **Time-boxed** | Conditional use granted for a fixed window; unclosed findings revert the component to a conservative SA fallback |

> **Regime-profile identifiers.** "US NPR" is the prose shorthand used throughout
> this document. The implemented profile **enum identifiers differ by package**:
> `frtb-ima` uses `RegulatoryRegime.FED_NPR_2_0` (with `ECB_CRR3` and `PRA_UK_CRR`
> for the EU/UK variants); the Standardised-Approach and CVA packages (`frtb-sbm`,
> `frtb-drc`, `frtb-cva`) use `US_NPR_2_0` (with `BASEL_MAR21`). Where this document
> names a code identifier it uses the package-correct enum value.

---

## 1. Purpose and scope

This TOM answers five questions for an FRTB programme that uses `frtb-capital`:

1. **Who** runs **what**, and **when**? (organisational + functional model)
2. What is computed **upfront** (configuration, calibration, onboarding) vs **live**
   (daily/intraday capital) vs **periodically** (quarterly recalibration, annual
   review)?
3. What is **reported**, **to whom**, **when**, and **how**?
4. How does this **library** interact with the **risk engine**, the **finance
   engine**, and **capital reporting**?
5. What does **regulation** require, and what must **Model Risk Management (MRM)**
   independently check?

Scope: market-risk capital under FRTB — **IMA + Standardised Approach (SBM + DRC
+ RRAO) + CVA**, under the **US NPR** regime (decision 1). The operating model is
**designed for full IMA + SA from day one** (decision 2): every role, process, and
evidence flow below is present at go-live. **Capital-of-record, however, rolls out
SA first** (decision 17) — SBM + DRC + RRAO (+ CVA) become the official numbers
first, and **IMA is switched on desk-by-desk** as each desk's PLA / backtesting
evidence matures and Market Risk approves eligibility. Out of scope: counterparty
credit (SA-CCR/IMM), banking-book IRRBB, and non-market RWA.

---

## 2. System context — where this library sits

`frtb-capital` is a **calculation engine library**, not a platform. It consumes
risk-factor and sensitivity inputs, produces auditable capital results, and hands
them to downstream stores and reporting. It deliberately does **not** own market
data, P&L production, trade capture, or the regulatory return itself.

```mermaid
flowchart TB
    subgraph FO["Front Office"]
        TC["Trade capture<br/>& booking"]
        MM["Market making<br/>/ desk risk"]
    end

    subgraph SRC["Source & market data"]
        MD["Market data<br/>(curves, vols, prices)"]
        REF["Reference data<br/>(issuers, ratings, buckets)"]
    end

    subgraph OBS["Observation & eligibility data (NOT the risk engine)"]
        VPOOL["Vendor real-price-observation pools<br/>(S&P/IHS Markit RFE,<br/>Bloomberg, data-pooling services)"]
        IOBS["Internal observability DB<br/>(own executed trades,<br/>committed quotes, observed prices)"]
    end

    subgraph RE["In-house Risk Engine (Quant)"]
        PNL["10-day scenario P&L<br/>(for ES/IMCC)"]
        SENS["Sensitivities<br/>(CRIF / delta / vega / curvature)"]
        VEC["HPL / RTPL & backtest<br/>P&L vectors (for PLA/BT)"]
    end

    subgraph LIB["frtb-capital library (THIS REPO)"]
        IMA["frtb-ima"]
        SBM["frtb-sbm"]
        DRC["frtb-drc"]
        RRAO["frtb-rrao"]
        CVA["frtb-cva"]
        ORCH["frtb-orchestration<br/>(suite aggregation)"]
    end

    subgraph STORE["Evidence & serving"]
        RS["frtb-result-store<br/>(DuckDB/Parquet,<br/>lineage, attribution)"]
    end

    subgraph FIN["Finance Engine & Reporting"]
        GL["Capital / RWA ledger"]
        REG["Regulatory reporting<br/>(US FFIEC)"]
        MI["Management information<br/>& limits"]
    end

    subgraph GOV["Independent oversight"]
        MRM["Model Risk Mgmt<br/>(SR 11-7 / SS 1/23)"]
        IA["Internal Audit"]
    end

    TC --> SRC
    MM --> SRC
    SRC --> RE
    RE -->|"sensitivities, scenario P&L,<br/>HPL/RTPL vectors"| LIB
    OBS -->|"real price observations<br/>(RFET evidence)"| LIB
    IMA --> ORCH
    SBM --> ORCH
    DRC --> ORCH
    RRAO --> ORCH
    CVA --> ORCH
    ORCH --> RS
    RS --> FIN
    GL --> REG
    GL --> MI
    MRM -.validates.-> LIB
    MRM -.validates.-> RE
    IA -.audits.-> FIN
```

**Key boundary principle.** Three different upstream owners feed the library — do
not collapse them:

1. **The in-house risk engine** produces *quantitative vectors*: sensitivities /
   CRIF, 10-day scenario P&L, and the **HPL / RTPL** and backtest P&L series. It
   does **not** decide modellability or run the regulatory tests.
2. **Observation & eligibility data** (RFET evidence) comes from a *separate
   data-sourcing function* — vendor real-price-observation pools (e.g. the
   S&P/IHS Markit Risk Factor Eligibility service, Bloomberg, industry
   data-pooling utilities) plus the bank's **internal observability database** of
   its own executed trades, committed quotes, and observed prices. This is a
   market-/risk-data curation responsibility, not a risk-engine output.
3. **`frtb-capital`** owns the *regulatory transform*: it runs the RFET, derives
   NMRFs and SES, runs the PLA/backtesting tests on the vectors, and computes
   capital — with the audit trail.

Finance owns the *ledger, return, and disclosure*. The Arrow/Parquet handoff
([ADR 0023](decisions/0023-arrow-tabular-handoff-boundary.md)) is the contractual
seam for both the risk-engine feed and the observation-data feed. The provenance
of RFET / NMRF / PLA evidence is detailed in **§4.4**.

---

## 3. Organisational model — who owns what

Six functions interact across the FRTB lifecycle. The library is a shared asset;
ownership is about *the activity*, not the code.

| Function | Primary FRTB responsibility |
| --- | --- |
| **Front Office (FO)** | Accurate, timely trade booking; desk structure and desk-boundary proposals; first-line explanation of capital moves; remediation of booking/feed breaks. |
| **Quant (front-office or central modelling)** | Pricing models and the risk-factor/sensitivity production that feeds the library; the **HPL/RTPL and backtest P&L vectors**; NMRF classification methodology; methodology proposals (ADRs). |
| **Market / Risk Data function** | Sources and curates **RFET real-price-observation evidence** from vendor pools and the internal observability database; maintains the reduced-data-set history; owns observation data quality. |
| **Risk (2nd line — Market Risk)** | Owns the risk appetite, limits, desk IMA eligibility decisions, and sign-off that capital is fit for limit/decision use; challenges FO explanations. |
| **Risk Analytics** | **Centralised, sitting in 2LOD under the CRO** (decision 4, 9). Operates the capital production run suite-wide: configures regimes/profiles, executes the library, reconciles SA vs IMA, investigates breaks, produces attribution, and issues the signed-off capital extract to Finance. Day-to-day "run the engine" owner, structurally independent of the front office. |
| **Finance** | Owns capital/RWA in the ledger, the **US FFIEC regulatory return**, capital adequacy disclosure, and the reconciliation of risk-produced capital to the general ledger. |
| **IT / Platform Engineering** | Owns the runtime platform, data pipelines, scheduling, environment/version control, the result store, access control, and SDLC for the library deployment. |
| **Model Risk Management (MRM)** | Independent validation of each capital component as a model (SR 11-7); ongoing monitoring; approval and conditional-use gates. |

### Responsibility matrix (plain language — no RACI)

Each row reads as a sentence: **one role leads** (does the work and owns the
outcome), other roles **help** (provide inputs or expertise), **one role signs it
off** (the accountable approver), and some roles are simply **kept informed**. If
a role isn't listed in a row, it has no part in that activity.

| Activity | Leads (does the work) | Helps | Signs it off | Kept informed |
| --- | --- | --- | --- | --- |
| Desk structure / boundary definition | Front Office | Risk Analytics, Quant | Market Risk (2LOD) | Finance, MRM |
| Pricing, sensitivities & P&L/HPL/RTPL vectors | Quant | Risk Analytics | Quant head | Market Risk |
| RFET observation sourcing & curation | Market/Risk Data | Quant, vendors | Market Risk (2LOD) | Risk Analytics |
| Methodology / regime config (ADRs) | Quant | Risk Analytics, MRM | Market Risk (2LOD) | Finance |
| Daily capital run execution | Risk Analytics | IT (platform) | Risk Analytics head | Market Risk |
| RFET → NMRF → SES determination | Risk Analytics *(runs library)* | Quant *(classification)* | Market Risk (2LOD) | MRM |
| PLA / backtesting → desk eligibility | Risk Analytics *(runs library)* | Quant *(vectors)* | Market Risk (2LOD) | FO, MRM |
| Reconciliation (SA↔IMA, risk↔finance) | Risk Analytics | Finance | Risk Analytics head | Market Risk |
| Period capital sign-off | Risk Analytics | Finance | Market Risk (2LOD) | ExCo |
| Controlled handover to Finance | Risk Analytics | — | Finance | MRM |
| US FFIEC regulatory return | Finance | Risk Analytics | Finance head | Market Risk |
| Independent model validation | MRM | Quant, Risk Analytics | MRM head / CRO | Board Risk Cttee |
| Platform / version / access control | IT | Risk Analytics | IT head | MRM |

> **Note on the library's role.** Where a row says "Risk Analytics *(runs
> library)*", the **regulatory test itself is performed by `frtb-capital`** —
> Risk Analytics operates it and owns the result, but the RFET, the NMRF/SES
> derivation, and the PLA/backtesting metrics are computed by the library using
> the prescribed regulatory methodology, not hand-calculated. See §4.4.

---

## 4. Functional model — upfront vs live vs periodic

FRTB has three distinct cadences. The library supports all three but is invoked
differently in each.

```mermaid
flowchart LR
    subgraph UP["UPFRONT (onboarding / change)"]
        U1["Desk boundary &<br/>IMA eligibility setup"]
        U2["Regime / jurisdiction<br/>profile config"]
        U3["Reference data &<br/>bucket calibration"]
        U4["Stress-period &<br/>NMRF spec selection"]
        U5["Input contract<br/>(Arrow specs) onboarding"]
    end

    subgraph LIVE["LIVE (daily / T+1)"]
        L1["Ingest sensitivities<br/>& P&L vectors"]
        L2["Run SBM/DRC/RRAO<br/>+ IMA + CVA"]
        L3["Orchestrate suite<br/>capital + fallback"]
        L4["Reconcile & attribute"]
        L5["Persist to result store"]
    end

    subgraph PER["PERIODIC"]
        P1["Quarterly stress-period<br/>recalibration"]
        P2["PLA / backtesting<br/>desk eligibility (quarterly)"]
        P3["Annual model review<br/>(MRM)"]
        P4["Regulatory return<br/>(monthly/quarterly)"]
    end

    UP --> LIVE
    LIVE --> PER
    PER -.feeds back config.-> UP
```

### 4.1 Upfront (run once per onboarding or per change)

| Activity | Owner | Library touchpoint |
| --- | --- | --- |
| Desk boundary & IMA-eligibility policy | Risk + FO | `DeskEligibilityStatus`, two-state guard (ADR 0009) |
| Jurisdiction/regime profile selection (`FED_NPR_2_0`/`ECB_CRR3`/`PRA_UK_CRR` in frtb-ima; `US_NPR_2_0`/`BASEL_MAR21` in SA & CVA) | Quant + Risk | `regimes.py` per package; profile guards (ADR 0022) |
| Reference data load (buckets, weights, correlations) | Risk Analytics | package `*_reference_data.py` rule tables |
| RFET observation-feed onboarding (vendor pools + internal observability DB) | Market/Risk Data + IT | RFET evidence input specs (see §4.4) |
| Reduced-data-set selection (modellable factors w/ stress history) | Quant + Market/Risk Data | ES stress-scaling inputs |
| Stress-period & NMRF stress spec; Type A/B classification rules | Quant | `frtb_ima.stress_periods`, `frtb_ima.nmrf_stress_spec`; Type A/B via `frtb_ima.nmrf.route_nmrf_classifications_for_capital` + `NMRFTaxonomyMode` |
| Input contract onboarding (column specs, hashing) | IT + Risk Analytics | `*_ARROW_COLUMN_SPECS`, CRIF normalization |

### 4.2 Live (daily, typically T+1 batch)

The daily run is the heart of the operating model:

```mermaid
sequenceDiagram
    autonumber
    participant RE as Risk Engine
    participant OBS as Obs/Eligibility Data
    participant LIB as frtb-capital
    participant ORCH as Orchestration
    participant RS as Result Store
    participant RA as Risk Analytics
    participant FIN as Finance

    RE->>LIB: sensitivities, scenario P&L, HPL/RTPL vectors
    OBS->>LIB: curated real price observations (RFET evidence)
    Note over LIB: normalize → batch → kernels → frozen result records
    Note over LIB: RFET → NMRF/SES; PLA + backtest → eligibility (§4.4)
    LIB->>LIB: SBM + DRC + RRAO (SA components)
    LIB->>LIB: IMA (model-eligible desks)
    LIB->>LIB: CVA
    LIB->>ORCH: ComponentCapitalSummary handoffs
    ORCH->>ORCH: SA arithmetic + IMA fallback routing (ADR 0032)
    ORCH->>ORCH: calculate_suite_capital = IMA + SA + CVA (ADR 0039)
    ORCH->>RS: persist run, lineage, attribution
    RS->>RA: drilldown + reconciliation views
    RA->>RA: SA↔IMA reconciliation, break investigation
    RA->>FIN: controlled file handover — reviewed, signed-off extract
    FIN->>FIN: ingest, post to capital ledger / RWA, assemble FFIEC return
```

### 4.3 Periodic

| Activity | Cadence | Owner |
| --- | --- | --- |
| Stress-period recalibration | Quarterly (or on trigger) | Quant |
| PLA traffic-light + backtesting exceptions → desk eligibility | Quarterly | **Market Risk (2LOD)** decides directly off library output (decision 13) |
| Capital impact attribution / methodology change validation | Per change | Risk Analytics + MRM |
| Annual model validation & periodic review | Annual | MRM |
| **Methodology / regime release train** (bundled ADRs, parallel-run, cutover) | **Quarterly** (emergency patches exception-only) | Risk Analytics + Quant + MRM |
| US FRTB regulatory return (FFIEC) | Monthly / quarterly | Finance |

> **Change management (decisions 10, 16).** Methodology and regime-profile changes
> (new ADRs, weight/correlation updates, US-NPR profile changes) are bundled
> onto a **quarterly scheduled release train**. Each change runs **one month in
> parallel against the incumbent** before cutover so the capital impact is
> attributable (ADR 0012 / 0038) and reviewable by MRM and Finance. Regulatory-
> mandated fixes and defect patches may take an exception fast track outside the
> train.

### 4.4 IMA evidence provenance — RFET → NMRF → SES, and PLA / backtesting

This is the most commonly misunderstood part of the operating model, so it is set
out explicitly. **The risk engine is not the source of eligibility evidence.**
Two different things flow into the library and the library — not the upstream
systems — performs the regulatory determinations.

```mermaid
flowchart TB
    subgraph SRCDATA["Data sources (who provides the raw evidence)"]
        V["Vendor real-price-observation pools<br/>(S&P/IHS Markit RFE service,<br/>Bloomberg, data-pooling utilities)"]
        I["Internal observability DB<br/>(own executed trades, committed<br/>quotes, observed prices)"]
        Q["In-house risk engine (Quant)<br/>HPL · RTPL · backtest P&L vectors"]
    end

    subgraph DATAFN["Market / Risk Data function"]
        CUR["Curate & de-duplicate<br/>real price observations<br/>per risk factor + timestamp"]
        RED["Maintain reduced-data-set<br/>long history for stress period"]
    end

    subgraph LIBFN["frtb-capital (regulatory transform)"]
        RFET["RFET: count obs, check<br/>max gap → modellable?"]
        NMRF["Fail ⇒ NMRF;<br/>classify Type A vs Type B"]
        SES["SES: stress scenario per NMRF,<br/>liquidity horizon, aggregation"]
        ES["ES / IMCC on modellable<br/>set (full + reduced)"]
        PLA["PLA test (Spearman + KS)<br/>+ backtesting exceptions"]
        ELIG["Desk eligibility<br/>traffic-light"]
    end

    V --> CUR
    I --> CUR
    CUR --> RFET
    RED --> ES
    RFET -->|pass| ES
    RFET -->|fail| NMRF
    NMRF --> SES
    Q --> PLA
    PLA --> ELIG
    ELIG -.->|red ⇒ desk loses IMA| ES
```

**Step-by-step, with the owner of each step:**

| Step | What happens | Raw data from | Decision / computation owner |
| --- | --- | --- | --- |
| 1. Observation sourcing | Real price observations gathered per risk factor (date, price, source). Vendors supply pooled industry observations; the internal observability DB supplies the bank's own executed trades and committed quotes. | **Vendor RPO pools + internal observability DB** (not the risk engine) | **Market/Risk Data function** curates; quality-owned in 2LOD |
| 2. RFET (modellability) | Count observations over the window and check the maximum gap against the US-NPR criteria; a risk factor (or bucket) passes or fails. | Curated observations | **`frtb-capital`** (`frtb_ima.rfet_evidence`) runs the test; Risk Analytics operates it |
| 3. NMRF derivation | Every risk factor that **fails** RFET is non-modellable ⇒ an NMRF. This follows *mechanically* from RFET — there is no separate "is it an NMRF" decision. | RFET output | **`frtb-capital`** derives the set automatically |
| 4. NMRF classification (Type A vs B) | *This* is where judgment enters. Idiosyncratic credit/equity NMRFs that meet the criteria are **Type A** (aggregated assuming **zero correlation**, ADR 0006); all others are **Type B** (prescribed correlation). | Risk-factor taxonomy + idiosyncratic-eligibility flags | **Quant** sets the classification methodology; **`frtb-capital`** applies it (`frtb_ima.nmrf.route_nmrf_classifications_for_capital`, `NMRFTaxonomyMode`) |
| 5. SES | Each NMRF gets a stress-scenario shock, a liquidity horizon, and is aggregated into the Stressed Expected Shortfall add-on. | Stress-period calibration spec | **`frtb-capital`** — calibration via `frtb_ima.nmrf_stress_spec` / `stress_periods`, SES aggregation via `frtb_ima.nmrf.calculate_nmrf_capital_for_policy` / `aggregate_ses_breakdown_for_policy`; **Quant** owns the calibration |
| 6. Reduced data set | The ES stress scaling (`ES = ES_{R,S} · ES_{F,C} / ES_{R,C}`) needs a **reduced set of modellable risk factors** with long enough history for the stress period (must capture ≥ the regulatory share of full ES). This is a *data-availability selection among modellable factors* — related to, but distinct from, RFET. | Long-history market data | **Market/Risk Data** maintains the history; **Quant** selects the reduced set; **`frtb-capital`** computes the ratios |
| 7. PLA | The risk engine supplies **HPL** (hypothetical, full-reval P&L) and **RTPL** (risk-theoretical P&L). The library runs the **regulatory PLA test** — Spearman correlation and the KS statistic — and assigns the green/amber/red zone. | **Risk engine HPL/RTPL vectors** | **`frtb-capital`** (`frtb_ima.pla`) runs the test using regulator methodology; Quant owns the vectors |
| 8. Backtesting & eligibility | Backtesting exceptions are counted from the P&L-vs-VaR vectors; combined with the PLA zone they drive **desk IMA eligibility**. A red desk falls back to SA (ADR 0009, 0032). | Risk engine P&L vectors | **`frtb-capital`** (`frtb_ima.backtesting`) computes; **Market Risk (2LOD)** owns the eligibility decision |

**Three corrections this section bakes in:**

1. **RFET evidence is not a risk-engine output.** It is curated observation data
   from **vendor pools + an internal observability database**, owned by a
   **Market/Risk Data** function. The risk engine never asserts modellability.
2. **NMRF follows directly from RFET** (fail ⇒ NMRF) — the *only* judgment is the
   **Type A vs Type B classification** and the SES stress calibration, both owned
   by Quant and applied by the library. The **reduced data set** is a separate
   stress-history selection among *modellable* factors, not an RFET output.
3. **PLA evidence is not a risk-engine verdict.** The risk engine provides **HPL
   and RTPL vectors**; **the library runs the PLA test** (Spearman + KS) and the
   backtesting count using the prescribed regulatory methodology.

**Sourcing model (decision 12 — internal-primary).** The **internal observability
database is the system of record** for real price observations: the bank captures
its own executed trades, committed quotes, and observed prices as the primary
modellability evidence, and **vendor pools fill the gaps** where the bank lacks
its own flow. This maximises the modellable set where the bank is a major
participant, at the cost of a substantial internal observation-capture build —
the curation, completeness, and vendor-gap reconciliation are owned by the
**Market/Risk Data** function in 2LOD.

**Thresholds (decision 11 — configurable per regime).** The RFET observation
count, maximum gap, observation window, and bucketing approach are **parameters of
the regime profile**, not hard-coded. The `FED_NPR_2_0` profile carries the US figures;
a Basel and an internal-conservative variant coexist and are selected at config
time. The exact US-NPR threshold values and the Type A/B idiosyncratic-NMRF
criteria still need to be pinned against the rule text — tracked as O9 below.

---

## 5. Reporting — to whom, when, how

```mermaid
flowchart TB
    RUN["Daily capital run<br/>(result store)"] --> D1
    RUN --> D2
    RUN --> D3

    subgraph D1["Internal — daily/T+1"]
        DSK["Desk-level capital<br/>& attribution → FO heads"]
        LIM["Limit utilisation<br/>→ Market Risk (2LOD)"]
    end
    subgraph D2["Management — weekly/monthly"]
        EXCO["Capital MI pack<br/>→ ExCo / Risk Committee"]
        QC["PLA traffic-light<br/>→ desk eligibility board"]
    end
    subgraph D3["Regulatory — monthly/quarterly"]
        RET["FRTB capital return<br/>→ regulator (via Finance)"]
        PIL3["Pillar 3 disclosure"]
    end

    D1 --> ESC{"Break / breach?"}
    ESC -->|yes| INC["Escalation & remediation<br/>(FO + Risk Analytics)"]
```

| Report | Audience | Frequency | Channel / format |
| --- | --- | --- | --- |
| Desk capital + attribution drilldown | FO desk heads | Daily (T+1) | Result-store views / dashboard |
| SA↔IMA reconciliation & breaks | Risk Analytics, Market Risk | Daily | Reconciliation report |
| Limit utilisation vs appetite | Market Risk (2LOD) | Daily | Limits system feed |
| Capital MI pack | ExCo, Risk Committee | Weekly/Monthly | Finance MI |
| PLA traffic-light + backtest exceptions | Desk eligibility board, MRM | Quarterly | Eligibility report |
| FRTB regulatory return | Regulator | Monthly/Quarterly | COREP/FFIEC/PRA via Finance |
| Model performance & validation findings | Board Risk Committee | Annual + ad hoc | MRM report |

**How (mechanism):** every reported number traces to an immutable run in
`frtb-result-store` with a content/handoff hash, so any figure in a board pack or
a regulatory return can be drilled back to the inputs, the regime profile, and the
library version that produced it.

---

## 6. Library ↔ risk engine ↔ finance engine ↔ capital reporting

```mermaid
flowchart LR
    subgraph RISK["RISK ENGINE (upstream)"]
        direction TB
        R1["Pricing / revaluation"]
        R2["Sensitivity & CRIF<br/>production"]
        R3["10-day P&L scenario<br/>vectors"]
        R4["RFET / NMRF / PLA<br/>evidence"]
    end

    subgraph CAPLIB["frtb-capital (calculation)"]
        direction TB
        C1["Normalize & validate<br/>(fail-closed)"]
        C2["Capital kernels<br/>(NumPy, frozen results)"]
        C3["Orchestration &<br/>attribution"]
    end

    subgraph FINENG["FINANCE ENGINE (downstream)"]
        direction TB
        F1["Capital / RWA ledger"]
        F2["Recon risk↔GL"]
        F3["Regulatory return<br/>assembly"]
    end

    subgraph REP["CAPITAL REPORTING"]
        direction TB
        P1["Regulatory submission"]
        P2["Pillar 3 / disclosure"]
        P3["Management MI"]
    end

    RISK -->|"Arrow/Parquet<br/>contract"| CAPLIB
    CAPLIB -->|"frozen result<br/>records + lineage"| FINENG
    FINENG --> REP
    CAPLIB -.->|"drilldown / attribution"| REP
```

| Seam | Contract | Owner of contract |
| --- | --- | --- |
| Risk engine → library | Arrow column specs for sensitivities, scenario P&L, HPL/RTPL vectors + run context + content hash (ADR 0023, 0033) | Risk Analytics + IT |
| Observation data → library | Arrow column specs for curated real price observations (RFET evidence) | Market/Risk Data + IT |
| Library internal | `ComponentCapitalSummary` handoff (ADR 0029) | Library maintainers |
| Library → finance | **Controlled file handover**: reviewed, signed-off extract derived from frozen result records + `CapitalRunAuditLog` + lineage hash | Risk Analytics (produces) → Finance (ingests) |
| Finance → reporting | Ledger postings + US FFIEC return mapping | Finance |

> **Handover control (decisions 7, 15).** The risk↔finance boundary is a
> deliberate human gate, not a silent feed. Before sign-off, breaks (SA↔IMA,
> day-on-day moves, risk↔GL) are scored against **per-component RAG thresholds**:
> **green** passes automatically, **amber** requires a Risk Analytics explanatory
> note, and **red blocks the handover** until Market Risk (2LOD) approves. Risk
> Analytics then signs off the extract; Finance ingests it and owns the number
> from that point. The signed extract carries the run's content/handoff hash so
> Finance can always re-derive the lineage back to inputs, regime profile, and
> library version.

---

## 7. What the regulation requires (high level)

This TOM targets the **US NPR** as the binding regime (decision 1); the Basel MAR
references below are the conceptual lineage, but the authoritative numbers come
from the US final rule and the library's `US_NPR_2_0` profiles (DRC bucket taxonomy
and risk weights per ADRs 0024–0028).

| Requirement | Source (Basel lineage → US NPR) | Where it lands in this TOM |
| --- | --- | --- |
| Desk-level capital, desk boundary discipline | MAR (Basel), CRR3 (EU), US NPR | §3 desk structure; ADR 0009 |
| SA as floor / fallback for all desks | MAR20–22 | Orchestration SA fallback (ADR 0032) |
| IMA only for eligible desks (PLA + backtesting) | MAR32–33 | §4.3 quarterly eligibility |
| Expected Shortfall + liquidity horizons | MAR33 | `frtb-ima` ES, nested LH (ADR 0008) |
| NMRF capitalised via SES | MAR33 | `frtb_ima.nmrf`, SES (ADR 0006) |
| DRC for default risk | MAR22 | `frtb-drc` |
| RRAO for residual risks | MAR23 | `frtb-rrao` |
| CVA capital (BA-CVA / SA-CVA) | MAR50 | `frtb-cva` |
| Full audit trail / reproducibility | SR 11-7, SS 1/23 | result store, hashing, ADR log |

> Specific paragraph citations live in `docs/regulatory/` and each package's
> `REGULATORY_TRACEABILITY.md`. This table is a navigational map, not the
> authoritative citation source.

---

## 8. What Model Risk Management must check

MRM validates each component as an independent model under **SR 11-7** (the
binding US standard for this jurisdiction). Under decision 8, components may enter
**conditional production use with documented findings** and agreed remediation
timelines, which MRM tracks to closure rather than hard-gating every component
before first use.

**Conditional-use guardrail (decision 20 — time-boxed).** Conditional use is
granted for a **fixed window** (e.g. two quarters). If the findings are not closed
within the window, the component **reverts to a conservative fallback** — for a
market-risk component that means dropping the affected desk/scope back to the
**Standardised Approach** (consistent with the IMA→SA fallback in ADRs 0009 /
0032). This forces closure and bounds how long capital can rely on a model with
open findings, without needing a separate capital-overlay mechanism.

```mermaid
flowchart TB
    subgraph MRM["MRM validation dimensions"]
        V1["Conceptual soundness<br/>(methodology vs regulation)"]
        V2["Implementation testing<br/>(code ↔ spec, replication)"]
        V3["Data & input quality<br/>(completeness, RFET)"]
        V4["Outcomes analysis<br/>(benchmark / challenger)"]
        V5["Ongoing monitoring<br/>(PLA, backtest, stability)"]
        V6["Governance & controls<br/>(change, versioning, access)"]
    end
    V1 --> APPR{"Approve /<br/>conditional use + findings /<br/>reject"}
    V2 --> APPR
    V3 --> APPR
    V4 --> APPR
    V5 --> APPR
    V6 --> APPR
```

| Dimension | What MRM checks in this suite |
| --- | --- |
| Conceptual soundness | Regime profiles match cited regulation; ADRs justify every numerical choice |
| Implementation | Frozen-dataclass results, vectorised kernels, deterministic fixtures, replay tests |
| Data quality | Fail-closed validation, RFET evidence, NMRF identification completeness |
| Outcomes | Challenger-model reconciliation (`docs/validation/challenger_models.yml`) |
| Monitoring | PLA traffic-light, backtesting exceptions, capital attribution stability |
| Governance | Versioning, changelog fragments (ADR 0015), import-linter boundaries, result-store immutability |

---

## 9. Technical / deployment architecture (target)

**On-premise** (decision 6): compute runs on the bank's internal grid/scheduler,
co-located with the in-house risk engine, and the result store is on-prem storage.
No cloud dependency in the capital-of-record path.

```mermaid
flowchart TB
    subgraph DATA["Data tier"]
        MDP["Market data platform"]
        REFD["Reference data master"]
    end
    subgraph COMPUTE["Compute tier (on-prem grid)"]
        RENG["In-house risk engine grid<br/>(pricing, sensitivities)"]
        CAPJOB["Capital run job<br/>(frtb-capital, T+1 scheduled)"]
    end
    subgraph PERSIST["Persistence tier (on-prem)"]
        RSTORE["frtb-result-store<br/>(DuckDB / Parquet)"]
        ART["Artifacts & lineage"]
    end
    subgraph SERVE["Serving tier"]
        DASH["Capital dashboards"]
        FEED["Finance / reg-reporting feed"]
        API["Drilldown API"]
    end

    MDP --> RENG
    REFD --> RENG
    RENG -->|Arrow/Parquet| CAPJOB
    CAPJOB --> RSTORE
    CAPJOB --> ART
    RSTORE --> DASH
    RSTORE --> FEED
    RSTORE --> API
```

**Non-functional targets:** deterministic & reproducible runs (content hashing),
immutable run evidence, version-pinned library deployment, fail-closed on missing
reference data, separation of environments (dev/UAT/prod), and least-privilege
access to the result store.

**Run SLA & resilience (decision 14 — best-effort, no fallback).** The official
T+1 run executes when inputs are complete. If the risk-engine feed or the
observation-data feed is late or fails, the run **slips rather than substituting
stale or prior-day numbers** — correctness is prioritised over cadence. The
binding operational risk is therefore *feed reliability*; upstream feed SLAs and
monitoring (with alerting to Risk Analytics + IT) are the primary control, since
on-prem deployment offers no cloud elasticity to absorb a late batch.

**Retention & immutability (decision 18).** Every capital-of-record run is
retained **write-once (WORM) for 7 years** with full input lineage and content
hashes, supporting examiner drilldown back to inputs, regime profile, and library
version.

**Access & segregation of duties (decision 19 — role-based, environment-gated).**
Three role families — *methodology-config*, *run-execution*, *read* — are enforced
**per environment**. In production: regime/methodology config is **locked to the
release-train process** (no ad-hoc prod config), only the **IT scheduler triggers
official prod runs**, and all human users (Quant, Risk Analytics, FO, Finance,
MRM) are **read-only in prod**. This makes the 2LOD independence (decision 9)
technically enforced, not just organisational.

---

## 10. Decisions resolved and questions still open

Round-1 decisions are in §0; round-2 decisions resolved the operational questions
that round-1 raised. Status of the round-2 register:

| # | Question | Status |
| --- | --- | --- |
| O1 | T+1 run SLA & recovery path | **Resolved** → decision 14 (best-effort, no fallback; §9) |
| O2 | Desk IMA-eligibility governance | **Resolved** → decision 13 (Market Risk 2LOD decides; §4.3) |
| O3 | Break / sign-off thresholds | **Resolved** → decision 15 (tiered RAG per component; §6) |
| O4 | Parallel-run rules | **Resolved** → decision 16 (1 month parallel; §4.3) |
| O5 | Go-live sequencing | **Resolved** → decision 17 (SA first, then IMA per desk; §1) |
| O6 | Retention & immutability | **Resolved** → decision 18 (7-year WORM; §9) |
| O7 | Access & segregation of duties | **Resolved** → decision 19 (role-based, env-gated; §9) |
| O8 | Conditional-use cap | **Resolved** → decision 20 (time-boxed, reverts to SA; §8) |
| O9 | **US-NPR RFET & NMRF specifics** | **OPEN** — exact US observation thresholds/gap rules + Type A/B idiosyncratic criteria still need pinning to the rule text (parameterised slot exists per decision 11). |
| O10 | RFET observation-data sourcing | **Resolved (strategy)** → decision 12 (internal-primary). Remaining build detail: which specific vendor pool(s) and the internal-capture/reconciliation design. |

### Genuinely-open items for round 3

1. **O9 — US-NPR numeric calibration.** Pin the exact `FED_NPR_2_0` RFET thresholds and
   the Type A/B idiosyncratic-NMRF criteria against the final-rule text. This is a
   regulatory-sourcing task (Quant + regulatory traceability + MRM), not an
   organisational decision.
2. **O10 residual — observation-capture build.** Which vendor pool(s) supplement
   the internal observability DB, and the internal trade/quote-capture and
   vendor-gap reconciliation design.
3. **New: reduced-data-set selection criteria.** The ≥-share-of-full-ES rule and
   the governance for selecting/refreshing the reduced set (Quant + Market/Risk
   Data) — surfaced by §4.4 but not yet specified.

---

*Draft v0.4 — round-1 and round-2 decisions (1–20) incorporated and threaded
through §§1, 3, 4.3, 4.4, 6, 8, 9. One regulatory-sourcing item (O9) and two build-
detail items remain open for round 3.*
