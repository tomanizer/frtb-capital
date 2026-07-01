# GIRR Delta PRA UK CRR Fixture V1

Synthetic PRA_UK_CRR GIRR delta comparison-profile fixture for the first
PRA UK CRR SBM runtime cell.

Regulatory source:

- PRA PS1/26 Appendix 1 / PRA2026/1, Market Risk: Advanced Standardised
  Approach (CRR) Part, Articles 325c, 325h, and 325ae-325ag.

The fixture intentionally mirrors the numerical shape of the U.S. NPR GIRR
delta fixture while using PRA-owned citation ids, profile metadata, run ids,
input ids, profile hash, and input hash. Unsupported PRA cells remain
fail-closed and are covered by `invalid_cases.json`.
