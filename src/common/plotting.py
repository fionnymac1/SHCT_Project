"""Plotting (Task 1 + Task 2). Task 1: room air (T, humidity), and
AC/ventilation operation over each representative season-day, plus a
four-season overview. Task 2: AC performance-map contour plots over the
(T_room, T_amb) plane. Clean labels, units and legends (graded). Uses a
non-interactive backend."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from common import config

_MODE_NUM = {"OFF": 0, "VENT": 1, "AC": 2}
_MAP_LABELS = {"COP_inner": "$COP_{inner}$  [-]",
               "Q_AC_kW": "$\\dot{Q}_{AC}$  [kW]",
               "P_elec_kW": "$P_{elec}$  [kW]"}


def plot_season(r, path, label=None):
    """label: design description for the title, e.g. 'Propane, 40 mm'.
    Defaults to the Task-1 single-bore stand-in for backward compatibility."""
    if label is None:
        label = "%g mm / %s stand-in" % (config.STANDIN_BORE_MM, config.STANDIN_REFRIGERANT)
    th = r["t"] / 60.0
    fig, ax = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)

    # (1) room temperature + acceptable band + hysteresis setpoints
    ax[0].axhspan(config.T_BAND_LOW_C, config.T_BAND_HIGH_C,
                  color="tab:green", alpha=0.12,
                  label="acceptable %g-%g C"
                        % (config.T_BAND_LOW_C, config.T_BAND_HIGH_C))
    ax[0].plot(th, r["T"], color="tab:blue", lw=1.6, label="room T")
    ax[0].axhline(config.T_ON_C, color="0.5", ls=":", lw=0.9)
    ax[0].axhline(config.T_OFF_C, color="0.5", ls=":", lw=0.9,
                  label="ON %g / OFF %g" % (config.T_ON_C, config.T_OFF_C))
    ax[0].set_ylabel("temperature [C]")
    ax[0].set_title("Server room - %s day  (%s)" % (r["season"], label))
    _tlo = min(float(np.min(r["T"])), config.T_BAND_LOW_C)
    _thi = max(float(np.max(r["T"])), config.T_BAND_HIGH_C)
    _pad = 0.05 * (_thi - _tlo) + 0.5
    ax[0].set_ylim(_tlo - _pad, _thi + _pad)
    ax[0].legend(loc="upper right", fontsize=8)

    # (2) relative humidity (+ allowable band) and humidity ratio
    ax[1].axhspan(100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH,
                  color="tab:orange", alpha=0.08)
    ax[1].plot(th, 100 * r["phi"], color="tab:purple", lw=1.5, label="room RH")
    ax[1].axhline(100 * config.PHI_ALLOW_LOW, color="tab:red", ls="--", lw=0.9,
                  label="allowable 14-80 %")
    ax[1].axhline(100 * config.PHI_ALLOW_HIGH, color="tab:red", ls="--", lw=0.9)
    ax[1].set_ylabel("relative humidity [%]"); ax[1].set_ylim(0, 90)
    ax[1].legend(loc="upper right", fontsize=8)
    axb = ax[1].twinx()
    axb.plot(th, 1000 * r["X"], color="tab:cyan", ls=":", lw=1.3)
    axb.set_ylabel("humidity ratio X [g/kg]", color="tab:cyan")
    axb.tick_params(axis="y", labelcolor="tab:cyan")

    # (3) operating mode + cooling powers
    mode_num = np.array([_MODE_NUM[m] for m in r["mode"]])
    ax[2].step(th, mode_num, where="post", color="k", lw=1.3)
    ax[2].set_yticks([0, 1, 2]); ax[2].set_yticklabels(["OFF", "VENT", "AC"])
    ax[2].set_ylim(-0.3, 2.3); ax[2].set_ylabel("mode")
    axc = ax[2].twinx()
    axc.plot(th, r["Q_dem"], color="tab:red", lw=1.2, label="server load")
    axc.plot(th, r["Q_cool"], color="tab:blue", ls="--", lw=1.2, label="cooling delivered")
    axc.set_ylabel("power [kW]"); axc.set_ylim(0, max(8, r["Q_cool"].max() * 1.1))
    axc.legend(loc="upper right", fontsize=8)
    ax[2].set_xlabel("time of day [h]"); ax[2].set_xlim(0, 24)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_overview(R, path):
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    colors = {"winter": "tab:blue", "spring": "tab:green",
              "summer": "tab:red", "fall": "tab:orange"}
    ax[0].axhspan(config.T_BAND_LOW_C, config.T_BAND_HIGH_C,
                  color="0.85", alpha=0.6)
    for s in config.SEASONS:
        th = R[s]["t"] / 60.0
        ax[0].plot(th, R[s]["T"], color=colors[s], lw=1.3, label=s)
        ax[1].plot(th, 100 * R[s]["phi"], color=colors[s], lw=1.3, label=s)
    _allT = np.concatenate([R[s]["T"] for s in config.SEASONS])
    _tlo = min(float(_allT.min()), config.T_BAND_LOW_C)
    _thi = max(float(_allT.max()), config.T_BAND_HIGH_C)
    _pad = 0.05 * (_thi - _tlo) + 0.5
    ax[0].set_ylabel("room T [C]"); ax[0].set_ylim(_tlo - _pad, _thi + _pad)
    ax[0].set_title("Four representative days - room temperature & humidity")
    ax[0].legend(loc="upper right", ncol=4, fontsize=8)
    ax[1].axhline(100 * config.PHI_ALLOW_LOW, color="tab:red", ls="--", lw=0.9)
    ax[1].set_ylabel("room RH [%]"); ax[1].set_ylim(0, 90)
    ax[1].set_xlabel("time of day [h]"); ax[1].set_xlim(0, 24)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


# --------------------------------------------------------------- Task 2 maps
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
        plt.colorbar(cf, ax=ax).set_label(_MAP_LABELS.get(value, value))
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
    fig.colorbar(cf, ax=axes, label=_MAP_LABELS.get(value, value), shrink=0.85)
    if save:
        fig.savefig(f"perfmap_grid_{value}.png", dpi=150, bbox_inches="tight")
    return fig


# --------------------------------------------------------------- Task 3 sweep
def plot_design_comparison(df_compare, path, best=None):
    """Bar charts of the Task-3 selection criteria across all (refrigerant,
    bore) combinations: room-condition compliance, total electrical energy,
    and AC compressor start count. `best` = (refrigerant, bore_mm) to
    highlight; df_compare has one row per combo (see task3.sweep)."""
    df = df_compare.sort_values(["refrigerant", "bore_mm"])
    labels = [f"{r}\n{b:.0f} mm" for r, b in zip(df["refrigerant"], df["bore_mm"])]
    is_best = [(r, b) == best for r, b in zip(df["refrigerant"], df["bore_mm"])]
    colors = ["tab:orange" if b else "tab:blue" for b in is_best]
    x = np.arange(len(df))

    fig, ax = plt.subplots(3, 1, figsize=(max(7, 0.9 * len(df)), 8), sharex=True)

    ax[0].bar(x, 100 * df["frac_in_band"], color=colors)
    ax[0].axhline(100, color="0.6", ls=":", lw=0.9)
    ax[0].set_ylabel("time in band [%]")
    ax[0].set_title("Task 3 design comparison (orange = selected)")

    ax[1].bar(x, df["E_total_kWh"], color=colors)
    ax[1].set_ylabel("total electrical\nenergy [kWh / 4 days]")

    ax[2].bar(x, df["ac_starts_total"], color=colors)
    ax[2].set_ylabel("AC compressor\nstarts [4 days]")
    ax[2].set_xticks(x); ax[2].set_xticklabels(labels, fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
