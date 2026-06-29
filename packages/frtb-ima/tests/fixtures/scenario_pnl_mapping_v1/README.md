# Scenario P&L mapping fixture v1

Synthetic long-form scenario P&L rows for the first IMA scenario ingestion slice.
The fixture maps client-shaped CSV columns to `ima_scenario_pnl_vectors`, builds a
canonical accepted-row batch, and materializes a `ScenarioCube` for downstream
ES/LHA/IMCC paths. Values are converted to the cube convention where positive
values are losses; this fixture's source P&L uses positive-gain convention.

The default fixture is rectangular across scenario, position, and risk-factor
axes. Duplicate `(scenario_id, position_id, risk_factor_name)` rows are rejected
and reported. Sparse inputs are rejected by default unless the table mapping
explicitly declares `missing_cells: zero`.
