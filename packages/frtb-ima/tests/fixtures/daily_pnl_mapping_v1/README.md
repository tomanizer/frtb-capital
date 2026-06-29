# Daily P&L mapping v1 fixture

Synthetic first-slice fixture for issue #922. It demonstrates a minimal
client-shaped daily P&L export mapped into the v1 `ima_daily_pnl_vectors` target
through `mapping.yaml`.

The data is not client, vendor, or regulatory data. It is intentionally small:

- two desks;
- explicit APL/HPL/RTPL source columns;
- explicit 97.5% and 99.0% VaR columns;
- source row identifiers;
- one duplicate `desk_id` / `business_date` row that should be rejected by the
  generated validation report.
