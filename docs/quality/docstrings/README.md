# Docstring quality baseline

This directory stores the committed inventory baseline for runtime package
docstring gaps. The baseline is produced by:

```bash
make docstring-baseline
```

`make quality-control` compares the current inventory to
`baseline.json`. During the first ratchet, only new missing module docstrings and
new missing public API docstrings fail CI. NumPy section completeness and trivial
docstring findings remain in the baseline for package cleanup planning, but they
do not block new work yet.
