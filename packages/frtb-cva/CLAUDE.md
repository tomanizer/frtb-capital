# CLAUDE.md — frtb-cva

Review `frtb-cva` as the owner of CVA capital only.

## Delivered slice

- Reduced BA-CVA stand-alone and portfolio capital (`ba_cva.py`, `capital.py`).
- SA-CVA GIRR delta weighting and aggregation (`sa_cva.py`, `weighted_sensitivity.py`,
  `aggregation.py`, `risk_classes/girr.py`).
- Deterministic input hashing, audit serialization, and reconciliation (`audit.py`).

## Reject

- Silent zero-capital placeholders for unsupported methods.
- Sibling capital-package imports.
- Exposure-at-default or sensitivity shortcuts without cited calculation contracts.
- SA-CVA calls that accept BA-CVA counterparty/netting-set inputs without error.

## Unsupported (fail closed)

- Full BA-CVA hedge recognition (MAR50.17–26).
- SA-CVA risk classes other than GIRR delta.
- Mixed carve-out and materiality-threshold routing.
- U.S., EU, and UK comparison profiles.

See [`docs/REGULATORY_TRACEABILITY.md`](docs/REGULATORY_TRACEABILITY.md).
