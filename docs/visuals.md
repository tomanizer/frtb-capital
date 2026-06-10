# Visuals and diagrams

Visuals in this repository must help users and reviewers understand data contracts, capital flows, unsupported paths, and quantitative evidence. They are part of the audit surface, so they should be accurate, cited where they imply regulatory behavior, and easy to render in GitHub and CI.

All examples and notebook outputs are synthetic engineering and validation evidence, not final regulatory capital.

## Mermaid first

Use Mermaid for process, flow, sequence, architecture, decision, eligibility, handoff, and error-path diagrams. Prefer Mermaid when the visual explains how data moves or how a decision is made.

Good Mermaid use cases include:

- client risk-engine ETL to Arrow or dataclass handoff;
- CRIF normalization and package adapter routing;
- component calculation pipeline stages;
- IMA eligibility and fallback decisions;
- SA composition and suite top-of-house aggregation;
- result-store write, manifest, lineage, and query flows;
- unsupported-feature and fail-closed error paths.

Keep diagrams close to the public contract. Use package names and public entrypoints where possible, and avoid internal helper names unless the diagram is explicitly a maintainer deep dive.

## Quantitative charts

Use Matplotlib, Markdown tables, or plain text tables for quantitative evidence such as capital by component, desk, bucket, profile, add-on, sensitivity, or attribution source. Do not use Mermaid for numeric charts where the relative scale or exact value matters.

Matplotlib charts committed in notebooks should have:

- a clear title that names the synthetic data slice;
- axis labels with units or currency where applicable;
- readable tick labels and rotations for long category names;
- a restrained palette that works on light and dark GitHub themes;
- gridlines or value labels where they improve reading exact values;
- hidden top and right spines unless the chart type needs them;
- `tight_layout()` or equivalent layout control;
- no dependency on interactive display state;
- a nearby markdown caption explaining what the figure proves.

Prefer deterministic chart input ordering so notebook diffs remain stable. Avoid random colors and timestamp-dependent labels.

## Notebook standard

Notebook visuals should support the same teaching sequence in every package:

1. Show the raw input shape the upstream system must emit.
2. Show the public calculation or handoff entrypoint.
3. Show the result and audit or attribution evidence.
4. Show unsupported or rejected paths when that is part of the user contract.

The first visual in a teaching notebook should normally be a Mermaid flow or sequence diagram. Quantitative charts should appear after the calculation cell that produces the values they show.

For Matplotlib cells, prefer this baseline style unless a package notebook already defines a stricter local helper:

```python
import matplotlib.pyplot as plt

plt.rcParams.update(
    {
        "figure.dpi": 130,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "semibold",
    }
)
```

## Review checklist

When adding or changing diagrams and notebook charts, reviewers should check:

- the visual matches current code paths and public APIs;
- process diagrams are Mermaid unless a numeric chart is required;
- chart values come from executed synthetic examples or committed fixtures;
- captions and surrounding text do not present proposed-rule or comparison outputs as final regulatory capital;
- links from the notebook or document point to the owning package journey, public API, schema, or validation evidence;
- CI can run or smoke-test the notebook without interactive display requirements.

## Ownership

Package-local notebook visuals are owned by the package that owns the notebook. Suite-level onboarding and architecture visuals are owned by the suite documentation maintainers. When a visual describes regulatory treatment or unsupported behavior, update the owning traceability or support-matrix source first, then update the diagram.