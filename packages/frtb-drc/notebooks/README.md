# DRC Demonstration Notebooks

These notebooks are deterministic development artifacts for `frtb-drc`. They
use synthetic non-securitisation default-risk positions and committed fixture
outputs to demonstrate the public API, gross and net JTD mechanics, maturity
scaling, hedge benefit ratio, bucket capital, and scoped desk replay. They are
not final regulatory capital outputs.

Smoke-test the notebook code cells from the repository root with:

```bash
MPLBACKEND=Agg uv run --with nbmake --directory packages/frtb-drc pytest --nbmake notebooks
```

Open them interactively with any local Jupyter environment that can import the
workspace packages.

Current notebooks:

- `00_validation_map.ipynb` maps the `drc_nonsec_v2` notebook pack to committed
  fixture artifacts and regulatory anchors.
- `01_gross_jtd.ipynb` walks through gross jump-to-default calculations,
  seniority-specific LGD treatment, and P&L floors.
- `02_maturity_scaling.ipynb` demonstrates maturity-weight floors, the linear
  ramp, and full-weight positions before netting.
- `03_netting.ipynb` shows accepted and rejected issuer offsets under seniority
  constraints.
- `04_hbr_bucket_capital.ipynb` explains hedge benefit ratio mechanics,
  risk-weighted bucket capital, and bucket waterfalls.
- `05_category_capital.ipynb` reconciles category capital to golden outputs and
  shows scoped multi-desk replay.
