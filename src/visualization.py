import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

_LABELS = {"COP_inner": "$COP_{inner}$  [-]",
           "Q_AC_kW": "$\\dot{Q}_{AC}$  [kW]",
           "P_elec_kW": "$P_{elec}$  [kW]"}

def visualize_performance_map(df_map, refrigerant, D_bore, value="COP_inner",
                              ax=None, levels=12, show_points=True, save=False):
    """Filled-contour map of `value` over the source/sink plane:
       x = T_room (source), y = T_amb (sink), colour = value.
       `levels` may be an int or an explicit array (use an array to share a
       colour scale across subplots)."""
    grid = df_map.pivot(index="T_amb", columns="T_room", values=value)
    X, Y = np.meshgrid(grid.columns.values, grid.index.values)
    Z = grid.values

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(figsize=(6.5, 5))

    cf = ax.contourf(X, Y, Z, levels=levels, cmap="viridis")
    ax.contour(X, Y, Z, levels=levels, colors="k", linewidths=0.3, alpha=0.4)
    if show_points:
        ax.scatter(X, Y, s=6, facecolors="none", edgecolors="0.3", linewidths=0.4)

    ax.set_title(f"{refrigerant} — {D_bore:.0f} mm bore")
    if own_fig:
        ax.set_xlabel("$T_{room}$  [°C]   (source)")
        ax.set_ylabel("$T_{amb}$  [°C]   (sink)")
        plt.colorbar(cf, ax=ax).set_label(_LABELS.get(value, value))
        if save:
            fig.tight_layout()
            fig.savefig(f"perfmap_{refrigerant}_{D_bore:.0f}mm_{value}.png", dpi=150)
    return cf

def visualize_all_maps(maps, value="COP_inner", levels=12, save=False):
    """maps: dict {(refrigerant, D_bore): df_map}. Grid of contours, shared scale."""
    refrigerants = sorted({k[0] for k in maps})
    bores        = sorted({k[1] for k in maps})
    allv = pd.concat([df[value] for df in maps.values()])
    lev = np.linspace(allv.min(), allv.max(), levels + 1)

    fig, axes = plt.subplots(len(refrigerants), len(bores),
                             figsize=(4*len(bores), 3.3*len(refrigerants)),
                             sharex=True, sharey=True, squeeze=False)
    cf = None
    for i, ref in enumerate(refrigerants):
        for j, bore in enumerate(bores):
            ax = axes[i][j]; df = maps.get((ref, bore))
            if df is None: ax.axis("off"); continue
            cf = visualize_performance_map(df, ref, bore, value=value,
                                           ax=ax, levels=lev, show_points=False)
    for ax in axes[-1]:
        ax.set_xlabel("$T_{room}$ [°C]")
    for row in axes:
        row[0].set_ylabel("$T_{amb}$ [°C]")
    fig.colorbar(cf, ax=axes, label=_LABELS.get(value, value), shrink=0.85)
    if save:
        fig.savefig(f"perfmap_grid_{value}.png", dpi=150, bbox_inches="tight")
    return fig