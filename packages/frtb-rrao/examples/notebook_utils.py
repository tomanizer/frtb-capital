"""Notebook presentation helpers for the RRAO examples.

The helpers in this module are intentionally limited to notebook display and
example formatting. They are not part of the RRAO runtime capital kernel.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

RRAO_CLASSIFICATION_COLORS: dict[str, str] = {
    "EXOTIC": "#c43c39",
    "OTHER_RESIDUAL_RISK": "#d9902f",
    "SUPERVISOR_DIRECTED": "#7b61b9",
    "EXCLUDED": "#4d9a57",
}

RRAO_PROFILE_COLORS: dict[str, str] = {
    "BASEL": "#3f7fbf",
    "US_NPR": "#b85c2e",
    "FULL_BOOK": "#6c5aa8",
}


def setup_notebook_plot_style() -> None:
    """Apply the shared Matplotlib style used by RRAO notebooks."""

    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.alpha": 0.22,
            "grid.linestyle": "-",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "semibold",
            "axes.titlesize": 11,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "savefig.bbox": "tight",
        }
    )
