# Model-Validation Notebooks

These notebooks are deterministic development artifacts for the committed
`capital_run_v1` synthetic fixture. They are not regulatory reports and do not
claim final U.S. capital treatment.

Run them with:

```bash
make notebooks
```

Build the notebook-backed validation bundle with:

```bash
make validation-pack
```

Current slices:

- `00_validation_map.ipynb`
- `01_rfet_evidence_classification.ipynb`
- `02_stress_period_selection.ipynb`
- `03_lha_es_imcc.ipynb`
- `04_nmrf_chain.ipynb`
- `05_pla_backtesting.ipynb`
- `06_capital_assembly.ipynb`
