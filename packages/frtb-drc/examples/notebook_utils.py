"""Notebook presentation helpers for the DRC examples.

These helpers are display-only conveniences for example notebooks. They are not
part of the DRC runtime capital kernel.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

DRC_BUCKET_COLORS: dict[str, str] = {
    "CORPORATE": "#2563eb",
    "NON_US_SOVEREIGN": "#059669",
    "PSE_GSE": "#d97706",
    "DEFAULTED": "#dc2626",
}

DRC_SERIES_COLORS: dict[str, str] = {
    "long": "#2563eb",
    "short": "#f87171",
    "capital": "#059669",
    "neutral": "#64748b",
}


def setup_notebook_plot_style() -> None:
    """Apply the shared Matplotlib style used by DRC notebooks."""

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
