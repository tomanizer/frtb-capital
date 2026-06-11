"""Notebook plotting helpers for the FRTB IMA validation pack."""

from __future__ import annotations

from collections.abc import Mapping

IMA_CHART_COLORS: Mapping[str, str] = {
    "blue": "#4c78a8",
    "orange": "#f28e2b",
    "green": "#59a14f",
    "red": "#c44e52",
    "purple": "#6f4e7c",
    "amber": "#ffbf00",
    "black": "#111111",
    "dark_gray": "#333333",
    "light_gray": "#f2f2f2",
}

RFET_STATUS_PALETTE: Mapping[str, str] = {
    "MODELLABLE": IMA_CHART_COLORS["blue"],
    "TYPE_A_NMRF": IMA_CHART_COLORS["orange"],
    "TYPE_B_NMRF": IMA_CHART_COLORS["red"],
}


def apply_notebook_plot_style() -> None:
    """Apply the shared Matplotlib style for IMA validation notebooks."""

    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
