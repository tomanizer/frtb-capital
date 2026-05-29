"""Generate DRC demo notebooks.

Run from the frtb-drc package root:
    uv run python scripts/generate_notebooks.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "notebooks"


# ---------------------------------------------------------------------------
# Notebook helpers
# ---------------------------------------------------------------------------


def nb(cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def md(text: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text,
    }


_SETUP = """\
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib.pyplot as plt
from IPython.display import Markdown, display

from examples.drc_nonsec_fixture import load_drc_nonsec_v2_fixture, run_fixture_workflow
from frtb_drc.demo_data import ALL_POSITIONS, DEMO_CONTEXT

plt.rcParams.update(
    {
        "figure.dpi": 110,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def markdown_table(headers: list[str], rows: list[list[str]]) -> Markdown:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return Markdown("\\n".join([header, separator, *body]))


fixture = load_drc_nonsec_v2_fixture()
positions = fixture.positions
context = fixture.context
expected = fixture.expected_outputs
display(
    Markdown(
        f"Loaded fixture `{expected['fixture_id']}`: "
        f"`{len(positions)}` positions, "
        f"profile `{context.profile_id}`, "
        f"as-of `{context.calculation_date}`."
    )
)\
"""

# ---------------------------------------------------------------------------
# 00 — Validation map and regulatory framework
# ---------------------------------------------------------------------------

NB00 = nb(
    [
        md("""\
# 00 — Validation Map

Entry point for the `drc_nonsec_v2` demo notebook pack.  Maps each notebook to
the committed fixture artifacts and regulatory anchors.

**Prototype caution**: the fixture is deterministic synthetic development data.
These notebooks are model-validation evidence for this prototype only and do
not represent final regulatory capital figures."""),
        code(_SETUP),
        md("## Notebook map"),
        code("""\
rows = [
    ["00_validation_map.ipynb", "Pack index and regulatory framework", "positions.json, expected_outputs.json"],
    ["01_gross_jtd.ipynb", "LGD rules and gross JTD calculation", "positions.json, expected_outputs.json"],
    ["02_maturity_scaling.ipynb", "Maturity weighting floor and ramp", "positions.json, expected_outputs.json"],
    ["03_netting.ipynb", "Same-obligor netting and seniority constraints", "positions.json, expected_outputs.json"],
    ["04_hbr_bucket_capital.ipynb", "Hedge benefit ratio and bucket capital", "positions.json, expected_outputs.json"],
    ["05_category_capital.ipynb", "Category total and multi-desk analysis", "positions.json, expected_outputs.json"],
]
display(markdown_table(["Notebook", "Purpose", "Fixture inputs"], rows))\
"""),
        md("""\
## Regulatory anchors

US NPR 2.0 (91 FR 14952) is the primary profile.  Basel FRTB (MAR22) is the
conceptual baseline.

| Step | Rule ref | Description |
|------|----------|-------------|
| Gross JTD | § 210(b)(1)(iv) / MAR22.11-13 | LGD * notional + P&L component |
| Maturity weight | § 210(a)(2)(iii) / MAR22.12 | Floor 0.25 Y, linear ramp to 1.0 Y |
| Netting | § 210(b)(2) / MAR22.14 | Same obligor, seniority constraint |
| HBR | § 210(a)(2)(iv)(A) / MAR22.17 | agg\_long / (agg\_long + agg\_short) |
| Bucket capital | § 210(a)(2)(iv)(C) / MAR22.19 | Σ(RW * long) - HBR * Σ(RW * short), ≥ 0 |
| Category total | § 210(b)(3)(iii) / MAR22.20 | Sum of bucket capitals |\
"""),
        md("## LGD rules (US NPR 2.0)"),
        code("""\
from frtb_drc.reference_data import iter_lgd_rules, US_NPR_2_0_PROFILE_ID

rows = [
    [rule.seniority.value, f"{rule.lgd_rate:.0%}", rule.citation_id, rule.description]
    for rule in iter_lgd_rules(US_NPR_2_0_PROFILE_ID)
]
display(markdown_table(["Seniority", "LGD", "Citation", "Description"], rows))\
"""),
        md("## Risk weights by bucket and credit quality (US NPR 2.0)"),
        code("""\
from frtb_drc.reference_data import iter_risk_weight_rules

rows = [
    [rule.bucket_key, rule.credit_quality.value, f"{rule.risk_weight:.1%}", rule.citation_id]
    for rule in iter_risk_weight_rules(US_NPR_2_0_PROFILE_ID)
]
display(markdown_table(["Bucket", "Credit quality", "Risk weight", "Citation"], rows))\
"""),
        md("## Portfolio summary"),
        code("""\
from collections import Counter

by_bucket = Counter(p.bucket_key for p in positions)
by_desk = Counter(p.desk_id for p in positions)
by_cq = Counter(p.credit_quality for p in positions)
by_dir = Counter(p.default_direction for p in positions)

print(f"Total positions : {len(positions)}")
print(f"By bucket       : {dict(sorted(by_bucket.items()))}")
print(f"By desk         : {dict(sorted(by_desk.items()))}")
print(f"By credit qual  : {dict(sorted(by_cq.items()))}")
print(f"By direction    : {dict(sorted(by_dir.items()))}")
print(f"Total DRC (USD) : {expected['total_drc']:,.2f}")\
"""),
    ]
)

# ---------------------------------------------------------------------------
# 01 — Gross JTD
# ---------------------------------------------------------------------------

NB01 = nb(
    [
        md("""\
# 01 — Gross Jump-to-Default

The gross JTD is the estimated loss if the issuer defaults today.

For a **LONG** position:

```
raw_jtd  = LGD * notional + P&L component
gross_jtd = max(raw_jtd, 0)
```

For a **SHORT** position:

```
raw_jtd  = LGD * (-notional) + P&L component
gross_jtd = abs(min(raw_jtd, 0))
```

The P&L component is `cumulative_pnl` if supplied; otherwise `market_value - notional` for LONG.

*Regulatory refs*: Basel MAR22.11-13; US NPR § 210(b)(1)(iv)\
"""),
        code(_SETUP),
        md("## Gross JTD across all seniority tiers"),
        code("""\
from frtb_drc.gross_jtd import calculate_gross_jtd
from frtb_drc.reference_data import US_NPR_2_0_PROFILE_ID

results = [calculate_gross_jtd(p, profile_id=US_NPR_2_0_PROFILE_ID) for p in positions]

rows = [
    [
        g.position_id,
        g.bucket_key,
        p.default_direction,
        p.seniority,
        f"{p.notional:>12,.0f}",
        f"{g.lgd_rate:.0%}",
        f"{p.cumulative_pnl or 0:>12,.0f}",
        f"{g.gross_jtd:>12,.2f}",
    ]
    for g, p in zip(results, positions)
    if g.gross_jtd > 0 or p.seniority in ("NOT_RECOVERY_LINKED",)
]
display(markdown_table(
    ["Position", "Bucket", "Dir", "Seniority", "Notional", "LGD", "PnL", "Gross JTD"],
    rows,
))\
"""),
        md("""\
## Special cases

### 1. NOT\_RECOVERY\_LINKED (LGD = 0)

`theta-pharma` holds a NOT\_RECOVERY\_LINKED instrument.  LGD = 0 → gross JTD = 0
regardless of notional.  The position contributes nothing to capital.\
"""),
        code("""\
theta = next(g for g in results if "theta" in g.position_id)
print(f"theta-pharma: notional={theta.notional:,.0f}  lgd={theta.lgd_rate:.0%}  gross_jtd={theta.gross_jtd:.2f}")\
"""),
        md("""\
### 2. Large negative P&L floors gross JTD to zero

`mu-industries` holds LONG SENIOR\_DEBT with a large unrealised loss
(`cumulative_pnl = -400 000`).

```
raw_jtd = 0.75 * 500 000 + (-400 000) = 375 000 - 400 000 = -25 000
gross_jtd = max(-25 000, 0) = 0
```\
"""),
        code("""\
mu_pos = next(p for p in positions if "mu" in p.position_id)
mu_g = next(g for g in results if "mu" in g.position_id)
print(
    f"mu-industries: notional={mu_pos.notional:,.0f}  lgd={mu_g.lgd_rate:.0%}"
    f"  pnl={mu_pos.cumulative_pnl:,.0f}  gross_jtd={mu_g.gross_jtd:.2f}"
)\
"""),
        md("""\
### 3. Positive P&L on a LONG position increases gross JTD

`delta-retail` has `cumulative_pnl = +80 000` (unrealised gain).
The bond is trading above par; the additional mark-to-market exposure is at risk on default.

```
raw_jtd = 1.0 * 600 000 + 80 000 = 680 000
```\
"""),
        code("""\
delta_pos = next(p for p in positions if "delta" in p.position_id)
delta_g = next(g for g in results if "delta" in g.position_id)
print(
    f"delta-retail: notional={delta_pos.notional:,.0f}  lgd={delta_g.lgd_rate:.0%}"
    f"  pnl={delta_pos.cumulative_pnl:,.0f}  gross_jtd={delta_g.gross_jtd:.2f}"
)\
"""),
        md("## Gross JTD chart — long positions by bucket"),
        code("""\
import matplotlib.pyplot as plt
import numpy as np

buckets = ["CORPORATE", "NON_US_SOVEREIGN", "PSE_GSE", "DEFAULTED"]
colours = ["#2563EB", "#059669", "#D97706", "#DC2626"]

fig, axes = plt.subplots(1, 4, figsize=(14, 4), sharey=False)
for ax, bucket, colour in zip(axes, buckets, colours):
    bucket_results = [
        (g.position_id.split("-", 2)[-1][:18], g.gross_jtd)
        for g, p in zip(results, positions)
        if p.bucket_key == bucket and p.default_direction == "LONG" and g.gross_jtd > 0
    ]
    if not bucket_results:
        ax.set_visible(False)
        continue
    labels, values = zip(*bucket_results)
    y = np.arange(len(labels))
    ax.barh(y, [v / 1e6 for v in values], color=colour, alpha=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Gross JTD (USD M)")
    ax.set_title(bucket, fontsize=9)

fig.suptitle("Gross JTD — long positions by bucket", fontsize=11)
fig.tight_layout()
plt.show()\
"""),
    ]
)

# ---------------------------------------------------------------------------
# 02 — Maturity scaling
# ---------------------------------------------------------------------------

NB02 = nb(
    [
        md("""\
# 02 — Maturity Scaling

Non-securitisation gross JTDs are scaled by a maturity weight before netting:

```
weight = 1.0                         if maturity >= 1.0 Y
weight = 0.25                        if maturity < 0.25 Y  (floor)
weight = (maturity - 0.25) / 0.75   if 0.25 ≤ maturity < 1.0 Y  (linear ramp)

scaled_jtd = gross_jtd * weight
```

*Regulatory refs*: Basel MAR22.12; US NPR § 210(a)(2)(iii)\
"""),
        code(_SETUP),
        md("## Maturity weight function"),
        code("""\
import numpy as np
import matplotlib.pyplot as plt

maturities = np.linspace(0, 2.5, 500)

def weight(m: float) -> float:
    if m < 0.25:
        return 0.25
    if m < 1.0:
        return (m - 0.25) / 0.75
    return 1.0

weights = [weight(m) for m in maturities]

fig, ax = plt.subplots(figsize=(7, 3.5))
ax.plot(maturities, weights, lw=2, color="#2563EB")
ax.axhline(0.25, ls="--", color="#94A3B8", lw=1, label="Floor (0.25)")
ax.axhline(1.0,  ls="--", color="#64748B", lw=1, label="Full weight (1.0)")
ax.axvline(0.25, ls=":", color="#CBD5E1", lw=1)
ax.axvline(1.0,  ls=":", color="#CBD5E1", lw=1)
ax.set_xlabel("Maturity (years)")
ax.set_ylabel("Maturity weight")
ax.set_title("Non-securitisation maturity weight (US NPR § 210(a)(2)(iii))")
ax.legend(fontsize=8)
fig.tight_layout()
plt.show()\
"""),
        md("""\
## beta-tech maturity ladder

The four `beta-tech` LONG SENIOR\_DEBT positions span 0.1 Y through 5.0 Y, demonstrating:

| Maturity | Regime | Weight |
|----------|--------|--------|
| 0.1 Y | Floor | 0.25 |
| 0.5 Y | Linear | 0.50 |
| 1.0 Y | Full weight | 1.00 |
| 5.0 Y | Full weight | 1.00 |\
"""),
        code("""\
from frtb_drc.gross_jtd import calculate_gross_jtd
from frtb_drc.maturity import scale_gross_jtd
from frtb_drc.reference_data import US_NPR_2_0_PROFILE_ID

beta_positions = [p for p in positions if "beta" in p.position_id]
rows = []
for p in sorted(beta_positions, key=lambda x: x.maturity_years):
    gross = calculate_gross_jtd(p, profile_id=US_NPR_2_0_PROFILE_ID)
    scaled = scale_gross_jtd(gross, p.maturity_years, profile_id=US_NPR_2_0_PROFILE_ID)
    rows.append([
        f"{p.maturity_years:.1f} Y",
        "floor" if scaled.floor_applied else ("full" if p.maturity_years >= 1.0 else "linear"),
        f"{scaled.maturity_weight:.4f}",
        f"{gross.gross_jtd:>12,.2f}",
        f"{scaled.scaled_jtd:>12,.2f}",
    ])

display(markdown_table(
    ["Maturity", "Regime", "Weight", "Gross JTD", "Scaled JTD"], rows
))\
"""),
        md("## All scaled JTDs"),
        code("""\
from frtb_drc.gross_jtd import calculate_gross_jtd
from frtb_drc.maturity import scale_gross_jtd

gross_results = [calculate_gross_jtd(p, profile_id=US_NPR_2_0_PROFILE_ID) for p in positions]
scaled_results = [
    scale_gross_jtd(g, p.maturity_years, profile_id=US_NPR_2_0_PROFILE_ID)
    for g, p in zip(gross_results, positions)
]

rows = [
    [
        s.position_id,
        p.bucket_key,
        f"{p.maturity_years:.2f}",
        f"{s.maturity_weight:.4f}",
        "Y" if s.floor_applied else "",
        f"{s.scaled_jtd:>12,.2f}",
    ]
    for s, p in zip(scaled_results, positions)
    if s.scaled_jtd > 0
]
display(markdown_table(
    ["Position", "Bucket", "Maturity (Y)", "Weight", "Floor?", "Scaled JTD"], rows
))\
"""),
        md("## Scaled JTD vs maturity scatter"),
        code("""\
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(7, 4))
for bucket, colour in [
    ("CORPORATE", "#2563EB"), ("NON_US_SOVEREIGN", "#059669"),
    ("PSE_GSE", "#D97706"), ("DEFAULTED", "#DC2626"),
]:
    xs = [p.maturity_years for p, s in zip(positions, scaled_results)
          if p.bucket_key == bucket and s.scaled_jtd > 0]
    ys = [s.scaled_jtd / 1e6 for p, s in zip(positions, scaled_results)
          if p.bucket_key == bucket and s.scaled_jtd > 0]
    ax.scatter(xs, ys, label=bucket, alpha=0.7, color=colour, s=60)

mats = np.linspace(0, 2.5, 200)
ws = [weight(m) for m in mats]
ax.set_xlabel("Maturity (years)")
ax.set_ylabel("Scaled JTD (USD M)")
ax.set_title("Scaled JTD vs maturity")
ax.legend(fontsize=8)
fig.tight_layout()
plt.show()\
"""),
    ]
)

# ---------------------------------------------------------------------------
# 03 — Netting
# ---------------------------------------------------------------------------

NB03 = nb(
    [
        md("""\
# 03 — Netting

Net JTD is computed per `(bucket_key, obligor)` group.  A SHORT position offsets
a LONG position for the same obligor only if the short's seniority rank is **at
least as junior** as the long's (i.e. `short_rank >= long_rank`).  A higher-
seniority short cannot offset a lower-seniority long — the offset is **rejected**
and both legs survive into the bucket capital step.

Seniority ranks (lower = higher seniority / lower LGD):

| Seniority | Rank |
|-----------|------|
| COVERED\_BOND, GSE\_GUARANTEED | 0 |
| SENIOR\_DEBT, GSE\_ISSUED\_NOT\_GUARANTEED, PSE | 1 |
| NON\_SENIOR\_DEBT | 2 |
| EQUITY | 3 |
| NOT\_RECOVERY\_LINKED | 4 |

*Regulatory refs*: Basel MAR22.14; US NPR § 210(b)(2)\
"""),
        code(_SETUP),
        md("## Net JTD records"),
        code("""\
from frtb_drc.gross_jtd import calculate_gross_jtds
from frtb_drc.maturity import scale_gross_jtds
from frtb_drc.netting import NettingInput, calculate_net_jtds
from frtb_drc.data_models import DrcSeniority

gross_jtds = calculate_gross_jtds(positions)
scaled_jtds = scale_gross_jtds(
    ((g, p.maturity_years) for g, p in zip(gross_jtds, positions))
)
pos_by_id = {p.position_id: p for p in positions}
gross_by_id = {g.position_id: g for g in gross_jtds}
scaled_by_id = {s.position_id: s for s in scaled_jtds}

netting_inputs = tuple(
    NettingInput(
        gross_jtd=gross_by_id[p.position_id],
        scaled_jtd=scaled_by_id[p.position_id],
        seniority=DrcSeniority(p.seniority),
    )
    for p in positions
    if p.seniority is not None
)
net_jtds = calculate_net_jtds(netting_inputs)

rows = [
    [
        net.net_jtd_id,
        net.bucket_key,
        net.net_direction.value,
        f"{net.net_amount:>14,.2f}",
        str(len(net.rejected_offsets)),
    ]
    for net in net_jtds
]
display(markdown_table(["Net JTD ID", "Bucket", "Direction", "Net amount", "Rejected offsets"], rows))\
"""),
        md("## Accepted offsets — acme-corp"),
        code("""\
# acme-corp: LONG SENIOR_DEBT (rank 1), SHORT NON_SENIOR_DEBT (rank 2)
# short_rank(2) >= long_rank(1) → ACCEPTED
acme_net = next(n for n in net_jtds if "acme" in n.net_jtd_id and n.net_direction.value == "LONG")
acme_long_p = pos_by_id["corp-acme-sr-l-001"]
acme_short_p = pos_by_id["corp-acme-nsr-s-001"]
print(f"LONG  seniority: {acme_long_p.seniority}  (rank 1)")
print(f"SHORT seniority: {acme_short_p.seniority}  (rank 2)")
print(f"short_rank(2) >= long_rank(1) → offset ACCEPTED")
print()
print(f"Scaled LONG  = {scaled_by_id['corp-acme-sr-l-001'].scaled_jtd:,.2f}")
print(f"Scaled SHORT = {scaled_by_id['corp-acme-nsr-s-001'].scaled_jtd:,.2f}")
print(f"Net amount   = {acme_net.net_amount:,.2f}  direction={acme_net.net_direction.value}")
print(f"Rejected offsets: {acme_net.rejected_offsets}")\
"""),
        md("""\
## Rejected offsets — eta-finance

`eta-finance` has LONG NON\_SENIOR\_DEBT (rank 2) and SHORT SENIOR\_DEBT (rank 1).
`short_rank(1) < long_rank(2)` → the short is **too senior** to offset the long.
Both survive as separate net positions.\
"""),
        code("""\
eta_nets = [n for n in net_jtds if "eta-finance" in n.net_jtd_id]
for net in eta_nets:
    print(f"  {net.net_jtd_id}: direction={net.net_direction.value}  amount={net.net_amount:,.2f}")
    for ro in net.rejected_offsets:
        print(f"    rejected: {ro.reason_code}")
print()
print("Interpretation:")
print("  eta-finance LONG NSR (rank 2) cannot be hedged by SENIOR_DEBT short (rank 1)")
print("  → both positions carry through to bucket capital step")\
"""),
        md("""\
## Rejected offsets — freddie-mac (PSE\_GSE bucket)

`freddie-mac` has LONG GSE\_ISSUED\_NOT\_GUARANTEED (rank 1) and SHORT GSE\_GUARANTEED (rank 0).
`short_rank(0) < long_rank(1)` → the short is **more senior** than the long → **rejected**.\
"""),
        code("""\
freddie_nets = [n for n in net_jtds if "freddie" in n.net_jtd_id]
for net in freddie_nets:
    print(f"  {net.net_jtd_id}: direction={net.net_direction.value}  amount={net.net_amount:,.2f}")
    for ro in net.rejected_offsets:
        print(f"    rejected: {ro.reason_code}")\
"""),
        md("## Netting: long vs short survivors by bucket"),
        code("""\
import matplotlib.pyplot as plt

buckets = ["CORPORATE", "NON_US_SOVEREIGN", "PSE_GSE", "DEFAULTED"]
colours = ["#2563EB", "#059669", "#D97706", "#DC2626"]
fig, axes = plt.subplots(1, 4, figsize=(14, 4))
for ax, bucket, colour in zip(axes, buckets, colours):
    longs = [n.net_amount / 1e6 for n in net_jtds
             if n.bucket_key == bucket and n.net_direction.value == "LONG"]
    shorts = [n.net_amount / 1e6 for n in net_jtds
              if n.bucket_key == bucket and n.net_direction.value == "SHORT"]
    ax.bar(["LONG", "SHORT"], [sum(longs), sum(shorts)], color=colour, alpha=0.8)
    ax.set_title(bucket, fontsize=9)
    ax.set_ylabel("Net JTD (USD M)")
fig.suptitle("Net JTD totals by bucket and direction", fontsize=11)
fig.tight_layout()
plt.show()\
"""),
    ]
)

# ---------------------------------------------------------------------------
# 04 — HBR and bucket capital
# ---------------------------------------------------------------------------

NB04 = nb(
    [
        md("""\
# 04 — Hedge Benefit Ratio and Bucket Capital

**Hedge benefit ratio** (HBR) for a bucket:

```
HBR = aggregate_net_long / (aggregate_net_long + aggregate_net_short)
```

If there are no net shorts after netting, HBR = 1.0 and the bucket has no hedge
benefit reduction.

**Bucket DRC capital** (risk-weighted, floored at zero):

```
capital = max( Σ(RW * long_net) - HBR * Σ(RW * short_net), 0 )
```

Risk weights: NON\_US\_SOVEREIGN IG=0.6 %, SG=22 %, sub-SG=50 %;
CORPORATE/PSE\_GSE IG=2.1 %, SG=22 %, sub-SG=50 %; DEFAULTED=100 %.

*Regulatory refs*: Basel MAR22.17-19; US NPR § 210(a)(2)(iv)\
"""),
        code(_SETUP),
        md("## Full pipeline to bucket capital"),
        code("""\
from frtb_drc.scaffold import calculate_drc_capital

result = calculate_drc_capital(positions, context=context)
cat = result.categories[0]

rows = [
    [
        b.bucket_key,
        f"{b.hbr.aggregate_net_long:>14,.2f}",
        f"{b.hbr.aggregate_net_short:>14,.2f}",
        f"{b.hbr.ratio:.6f}",
        f"{b.weighted_long:>14,.2f}",
        f"{b.weighted_short:>14,.2f}",
        f"{b.capital:>14,.2f}",
        "Y" if b.floor_applied else "",
    ]
    for b in cat.bucket_results
]
display(markdown_table(
    ["Bucket", "Agg net long", "Agg net short", "HBR", "W-long", "W-short", "Capital", "Floor?"],
    rows,
))\
"""),
        md("""\
## HBR mechanics

### CORPORATE — partial hedge

`eta-finance` and `zeta-metals` have REJECTED shorts that survive as net short
positions.  After risk-weighting:

- `weighted_short > 0` → HBR < 1.0
- Capital = weighted\_long - HBR * weighted\_short

The HBR ensures the hedge benefit is shared proportionally across longs and shorts.\
"""),
        code("""\
corp = next(b for b in cat.bucket_results if b.bucket_key == "CORPORATE")
print(f"CORPORATE")
print(f"  aggregate_net_long  = {corp.hbr.aggregate_net_long:,.2f}")
print(f"  aggregate_net_short = {corp.hbr.aggregate_net_short:,.2f}")
print(f"  HBR                 = {corp.hbr.ratio:.6f}")
print(f"  weighted_long       = {corp.weighted_long:,.2f}")
print(f"  weighted_short      = {corp.weighted_short:,.2f}")
print(f"  capital (unfloored) = {corp.weighted_long - corp.hbr.ratio * corp.weighted_short:,.2f}")
print(f"  capital (final)     = {corp.capital:,.2f}")\
"""),
        md("""\
### NON\_US\_SOVEREIGN — no net shorts after netting

UK, Japan, and Brazil shorts were fully consumed by their respective longs during netting.
No net short positions remain.  HBR = 1.0, but `weighted_short = 0` — so HBR has
no practical effect.\
"""),
        code("""\
sov = next(b for b in cat.bucket_results if b.bucket_key == "NON_US_SOVEREIGN")
print(f"NON_US_SOVEREIGN")
print(f"  aggregate_net_long  = {sov.hbr.aggregate_net_long:,.2f}")
print(f"  aggregate_net_short = {sov.hbr.aggregate_net_short:,.2f}")
print(f"  HBR                 = {sov.hbr.ratio:.6f}")
print(f"  capital             = {sov.capital:,.2f}")\
"""),
        md("## Bucket capital waterfall"),
        code("""\
import matplotlib.pyplot as plt
import numpy as np

labels = [b.bucket_key for b in cat.bucket_results]
w_longs = [b.weighted_long / 1e6 for b in cat.bucket_results]
w_shorts_reduced = [b.hbr.ratio * b.weighted_short / 1e6 for b in cat.bucket_results]
capitals = [b.capital / 1e6 for b in cat.bucket_results]

x = np.arange(len(labels))
width = 0.28

fig, ax = plt.subplots(figsize=(9, 4.5))
bars1 = ax.bar(x - width, w_longs, width, label="RW * net long", color="#2563EB", alpha=0.85)
bars2 = ax.bar(x, w_shorts_reduced, width, label="HBR * RW * net short", color="#F87171", alpha=0.85)
bars3 = ax.bar(x + width, capitals, width, label="Bucket capital", color="#059669", alpha=0.85)

ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
ax.set_ylabel("USD M")
ax.set_title("Bucket capital waterfall: RW * long - HBR * RW * short")
ax.legend(fontsize=8)
fig.tight_layout()
plt.show()\
"""),
    ]
)

# ---------------------------------------------------------------------------
# 05 — Category capital
# ---------------------------------------------------------------------------

NB05 = nb(
    [
        md("""\
# 05 — Category Capital and Multi-Desk Analysis

The non-securitisation category DRC is the **sum of all bucket capitals**.

This notebook:
1. Reconciles against the committed golden expected outputs.
2. Shows a multi-desk breakdown using scoped context runs (one desk at a time).

*Regulatory refs*: Basel MAR22.20; US NPR § 210(b)(3)(iii)\
"""),
        code(_SETUP),
        md("## Full capital assembly"),
        code("""\
from frtb_drc.scaffold import calculate_drc_capital

result = calculate_drc_capital(positions, context=context)
cat = result.categories[0]

print(f"Input count  : {result.input_count}")
print(f"Input hash   : {result.input_hash}")
print(f"Profile hash : {result.profile_hash}")
print()
for b in cat.bucket_results:
    print(f"  {b.bucket_key:<22}  capital = {b.capital:>14,.2f}  hbr = {b.hbr.ratio:.4f}")
print(f"  {'Category total':<22}  capital = {cat.capital:>14,.2f}")
print(f"  {'Total DRC':<22}  capital = {result.total_drc:>14,.2f}")\
"""),
        md("## Golden reconciliation"),
        code("""\
tolerance = 1e-9
checks = {
    "input_count"     : (result.input_count, expected["input_count"]),
    "input_hash"      : (result.input_hash, expected["input_hash"]),
    "profile_hash"    : (result.profile_hash, expected["profile_hash"]),
    "category_capital": (cat.capital, expected["category_capital"]),
    "total_drc"       : (result.total_drc, expected["total_drc"]),
}
rows = []
for name, (actual, golden) in checks.items():
    if isinstance(actual, float):
        ok = abs(actual - golden) < tolerance
        rows.append([name, f"{actual:,.4f}", f"{golden:,.4f}", "PASS" if ok else "FAIL"])
    else:
        ok = actual == golden
        rows.append([name, str(actual)[:40], str(golden)[:40], "PASS" if ok else "FAIL"])

display(markdown_table(["Check", "Actual", "Golden", "Status"], rows))\
"""),
        md("""\
## Multi-desk breakdown

The portfolio spans three desks:
- **credit-desk**: CORPORATE positions
- **rates-desk**: NON\_US\_SOVEREIGN positions
- **structured-desk**: PSE\_GSE and DEFAULTED positions

Each desk can be run independently using a scoped context (`desk_id` filter).\
"""),
        code("""\
from frtb_drc.data_models import DrcCalculationContext
import matplotlib.pyplot as plt

desks = ["credit-desk", "rates-desk", "structured-desk"]
desk_results = {}
for desk in desks:
    desk_context = DrcCalculationContext(
        run_id=f"demo-{desk}",
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=context.profile_id,
        desk_id=desk,
    )
    desk_positions = [p for p in positions if p.desk_id == desk]
    desk_results[desk] = calculate_drc_capital(desk_positions, context=desk_context)

rows = []
for desk, res in desk_results.items():
    cat_d = res.categories[0]
    for b in cat_d.bucket_results:
        rows.append([desk, b.bucket_key, f"{b.capital:>14,.2f}", f"{b.hbr.ratio:.4f}"])
    rows.append([desk, "TOTAL", f"{res.total_drc:>14,.2f}", ""])

display(markdown_table(["Desk", "Bucket", "Capital", "HBR"], rows))

# Verify desk totals sum to portfolio total
desk_total = sum(r.total_drc for r in desk_results.values())
portfolio_total = result.total_drc
print(f"\\nSum of desk capitals : {desk_total:,.2f}")
print(f"Portfolio total      : {portfolio_total:,.2f}")
print(f"Additive             : {abs(desk_total - portfolio_total) < 1e-9}")\
"""),
        md("## Capital by desk and bucket"),
        code("""\
import matplotlib.pyplot as plt
import numpy as np

all_buckets = ["CORPORATE", "NON_US_SOVEREIGN", "PSE_GSE", "DEFAULTED"]
colours = {"CORPORATE": "#2563EB", "NON_US_SOVEREIGN": "#059669",
           "PSE_GSE": "#D97706", "DEFAULTED": "#DC2626"}
desk_labels = desks

fig, ax = plt.subplots(figsize=(9, 4.5))
x = np.arange(len(desk_labels))
bottom = np.zeros(len(desk_labels))
for bucket in all_buckets:
    heights = []
    for desk in desk_labels:
        cat_d = desk_results[desk].categories[0]
        bkt_cap = next(
            (b.capital / 1e6 for b in cat_d.bucket_results if b.bucket_key == bucket), 0.0
        )
        heights.append(bkt_cap)
    ax.bar(x, heights, bottom=bottom, label=bucket, color=colours[bucket], alpha=0.85)
    bottom += np.array(heights)

ax.set_xticks(x)
ax.set_xticklabels(desk_labels, fontsize=10)
ax.set_ylabel("DRC capital (USD M)")
ax.set_title("DRC capital by desk and bucket")
ax.legend(fontsize=8, loc="upper right")
fig.tight_layout()
plt.show()\
"""),
        md("## Audit trail"),
        code("""\
from frtb_drc import result_json
import hashlib

rj = result_json(result)
sha = hashlib.sha256(bytes(rj, "utf-8")).hexdigest()
print(f"result_json SHA-256: {sha}")
print(f"Golden SHA-256:      {expected['result_json_sha256']}")
print(f"Match: {sha == expected['result_json_sha256']}")
print()
print(f"Citations used ({len(result.citations)}):")
for cit in result.citations:
    print(f"  {cit}")\
"""),
    ]
)


# ---------------------------------------------------------------------------
# Write notebooks
# ---------------------------------------------------------------------------


def write_nb(name: str, notebook: dict[str, Any]) -> None:
    path = OUT / name
    path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {path.name}  ({len(notebook['cells'])} cells)")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Writing notebooks to {OUT}")
    write_nb("00_validation_map.ipynb", NB00)
    write_nb("01_gross_jtd.ipynb", NB01)
    write_nb("02_maturity_scaling.ipynb", NB02)
    write_nb("03_netting.ipynb", NB03)
    write_nb("04_hbr_bucket_capital.ipynb", NB04)
    write_nb("05_category_capital.ipynb", NB05)
    print("Done.")
