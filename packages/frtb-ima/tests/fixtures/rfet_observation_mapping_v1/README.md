# RFET observation mapping v1 fixture

Synthetic second-slice fixture for client-data ingestion. It maps a small
client-shaped real-price observation export into the existing IMA RFET Arrow
observation target.

The fixture is deliberately narrow:

- two risk factors;
- source/vendor/venue/feed lineage;
- explicit source row identifiers;
- one rejected row with a missing risk factor name;
- no RFET modellability decision is inferred by the mapper.
