"""Plotting (Task 1 + Task 2). Task 1: room air (T, humidity), and
AC/ventilation operation over each representative season-day, plus a
four-season overview. Task 2: AC performance-map contour plots over the
(T_room, T_amb) plane. Clean labels, units and legends (graded). Uses a
non-interactive backend."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
import numpy as np
import pandas as pd
from common import config, eth_colormaps

# Default line/category colour cycle for any plot below that doesn't pass an
# explicit color= (the ones that do -- the vast majority -- read config.COLOR_*
# / config.ETH_QUAL_* instead, which are themselves sourced from this same
# palette; see config.py's "ETH colour scheme" section).
eth_colormaps.set_eth_cycle()

_MAP_LABELS = {"COP_inner": "$COP_{inner}$  [-]",
               "Q_AC_kW": "$\\dot{Q}_{AC}$  [kW]",
               "P_elec_kW": "$P_{elec}$  [kW]"}

# Task-2 contour map colour scale: per-quantity ETH sequential colormaps,
# replacing matplotlib's default "viridis". COP_inner and Q_AC_kW get their
# own hue (config.py) so the two map types stay visually distinct; anything
# else (e.g. P_elec_kW) falls back to the COP map's colour.
_TASK2_SEQUENTIAL_BY_VALUE = {
    "COP_inner": config.SEQUENTIAL_CMAP_COP,
    "Q_AC_kW": config.SEQUENTIAL_CMAP_Q_AC,
}


def _setpoint_traces(r):
    """The THREE control setpoints the run actually used at each step of r['t'],
    as arrays (T_OFF, T_ON_vent, T_ON_AC).

    The control law stages three temperature setpoints (cooling OFF / VENT on /
    AC on) and may shift the whole band DOWN with ambient via control.setpoints()
    (the constant SCHED_G offset + the SCHED_K ambient ramp). So the live
    setpoints are NOT the raw config.T_*_C constants, and with SCHED_K>0 they
    vary over the day -> they must be drawn per step, not as fixed config lines.
    Ambient is taken from r['T_amb'] if the sim stored it, else reconstructed
    from the same data_io source + resample the sim used (so it matches the run).
    Imported lazily to keep this plotting module free of any control/data import
    cost (and any package-init cycle) when only the Task-2/3 plots are used."""
    from common import data_io
    from task1 import control
    T_amb = r.get("T_amb")
    if T_amb is None:
        try:
            _, amb_raw = data_io.load_raw()
            _, T_amb = data_io.resample_day(amb_raw[r["season"]])
        except Exception:
            # Ambient unavailable: fall back to the schedule with a zero ramp
            # term (exact for SCHED_K=0, a sane stand-in otherwise) so the
            # figure still renders rather than crashing the whole plot.
            off, on, on_ac = control.setpoints(control.SCHED_T_STAR)
            n = len(r["t"])
            return np.full(n, off), np.full(n, on), np.full(n, on_ac)
    sp = np.array([control.setpoints(float(Ta)) for Ta in np.asarray(T_amb)])
    return sp[:, 0], sp[:, 1], sp[:, 2]


def _level_label(name, trace):
    """'name 22.5 C' when a setpoint is constant over the day, else the range
    'name 21.0-22.5 C' (an active ambient schedule, SCHED_K>0, moves it)."""
    lo, hi = float(np.min(trace)), float(np.max(trace))
    if hi - lo < 0.05:
        return "%s %.1f °C" % (name, lo)
    return "%s %.1f-%.1f °C" % (name, lo, hi)


def _mode_spans(t, mode, label):
    """[(t_start, t_end), ...] for each contiguous run of mode == label, in
    t's own units. Used to shade mode as a background band instead of a
    step line -- a step line of rapid OFF/VENT/AC switching just renders as
    a dense black smear, background shading reads cleanly at any switching
    frequency."""
    mode = np.asarray(mode)
    is_label = (mode == label)
    spans = []
    start = None
    for i, on in enumerate(is_label):
        if on and start is None:
            start = t[i]
        elif not on and start is not None:
            spans.append((start, t[i]))
            start = None
    if start is not None:
        spans.append((start, t[-1]))
    return spans


def plot_season(r, path, label=None):
    """label: design description for the title, e.g. 'Propane, 40 mm'.
    Defaults to the Task-1 single-bore stand-in for backward compatibility."""
    if label is None:
        label = "%g mm / %s stand-in" % (config.STANDIN_BORE_MM, config.STANDIN_REFRIGERANT)
    th = r["t"] / 60.0
    fig, ax2d = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    # [T, RH, DP, mode] -- humidity metrics (RH, DP) on the right column,
    # the others (T, mode/power) on the left; flat indexing below unchanged
    ax = [ax2d[0, 0], ax2d[0, 1], ax2d[1, 1], ax2d[1, 0]]

    # This figure uses its OWN arrangement of the ETH qualitative palette
    # (distinct from the project-wide config.COLOR_* mapping used by every
    # other plot), one colour per role: black = room T (the controlled
    # variable), blue = the cooling system (AC setpoint/spans, cooling
    # delivered), gold = VENT setpoint/spans, red = server load, grey =
    # cooling-OFF and the RH/dew-point lines, green = comfort/allowable bands.
    _BAND = config.ETH_QUAL_GREEN
    _BAND_ALLOWABLE = config.COLOR_RECOMMENDED_BAND_ALLOWABLE   # paired light-green outer tier (T)
    _HUMID_BAND = config.COLOR_HUMIDITY_BAND                      # purple (DP recommended tier)
    _HUMID_BAND_ALLOWABLE = config.COLOR_HUMIDITY_BAND_ALLOWABLE  # paired light-purple (RH + DP outer tier)
    _T_LINE = config.ETH_QUAL_BLACK
    _AC_SETPOINT, _VENT_SETPOINT, _OFF_SETPOINT = (
        config.ETH_QUAL_BLUE, config.ETH_QUAL_GOLD, config.ETH_QUAL_GREY)
    _RH_LINE, _RH_BAND = config.ETH_QUAL_GREY, _HUMID_BAND_ALLOWABLE
    _DP_LINE, _DP_BAND = config.ETH_QUAL_GREY, _HUMID_BAND
    _T_BAND = _BAND
    _AC_SHADE, _VENT_SHADE = config.ETH_QUAL_BLUE, config.ETH_QUAL_GOLD
    _LOAD_LINE, _COOL_LINE = config.ETH_QUAL_RED, config.ETH_QUAL_BLUE

    # (1) room temperature: fixed comfort/safety envelopes + the THREE control
    # setpoints the run ACTUALLY used (cooling OFF / VENT on / AC on). The
    # ambient schedule shifts these off the raw config.T_*_C constants (and with
    # SCHED_K>0 moves them through the day), so they are drawn per step from
    # control.setpoints() -- not as the old fixed config.T_ON/T_OFF lines.
    toff, ton, tonac = _setpoint_traces(r)
    # nested bands: allowable (wider, outer) drawn first, recommended (narrower,
    # inner) drawn on top -- PAIRED colours (base hue = recommended, paired
    # companion shade = allowable), not the same hue at two opacities.
    ax[0].axhspan(config.T_ALLOW_LOW_C, config.T_ALLOW_HIGH_C,
                  color=_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g °C" % (config.T_ALLOW_LOW_C, config.T_ALLOW_HIGH_C))
    ax[0].axhspan(config.T_RECOMMENDED_LOW_C, config.T_RECOMMENDED_HIGH_C,
                  color=_T_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="recommended %g-%g °C"
                        % (config.T_RECOMMENDED_LOW_C, config.T_RECOMMENDED_HIGH_C))
    # setpoints under the room-T line (room T plotted last -> stays on top)
    ax[0].step(th, tonac, where="post", color=_AC_SETPOINT, ls="--", lw=1.1,
               label=_level_label("AC on", tonac))
    ax[0].step(th, ton, where="post", color=_VENT_SETPOINT, ls="--", lw=1.1,
               label=_level_label("VENT on", ton))
    ax[0].step(th, toff, where="post", color=_OFF_SETPOINT, ls="--", lw=1.1,
               label=_level_label("cooling OFF", toff))
    ax[0].plot(th, r["T"], color=_T_LINE, lw=1.6, label="room T", zorder=6)
    ax[0].set_ylabel("temperature [°C]")
    fig.suptitle("Server room - %s day  (%s)" % (r["season"], label))
    _tlo = min(float(np.min(r["T"])), config.T_ALLOW_LOW_C)
    _thi = max(float(np.max(r["T"])), config.T_ALLOW_HIGH_C)
    _pad = 0.05 * (_thi - _tlo) + 0.5
    ax[0].set_ylim(_tlo - _pad, _thi + _pad)
    ax[0].legend(loc="upper right", fontsize=8, ncol=2)

    # (2) relative humidity (allowable band only -- no recommended target for
    # RH, so it uses the purple PARTNER shade directly -- the same outer tier
    # dew point's allowable uses below).
    ax[1].axhspan(100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH,
                  color=_RH_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g %%" % (100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH))
    ax[1].plot(th, 100 * r["phi"], color=_RH_LINE, lw=1.5, label="room RH")
    ax[1].set_ylabel("relative humidity [%]"); ax[1].set_ylim(0, 90)
    ax[1].legend(loc="upper right", fontsize=8)

    # (3) dew point. Allowable is pinned to literally equal RH's allowable
    # (same purple-partner colour as panel 2 above).
    ax[2].axhspan(config.DP_ALLOW_LOW_C, config.DP_ALLOW_HIGH_C,
                  color=_RH_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g °C" % (config.DP_ALLOW_LOW_C, config.DP_ALLOW_HIGH_C))
    ax[2].axhspan(config.DP_RECOMMENDED_LOW_C, config.DP_RECOMMENDED_HIGH_C,
                  color=_DP_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="recommended %g-%g °C" % (config.DP_RECOMMENDED_LOW_C, config.DP_RECOMMENDED_HIGH_C))
    ax[2].plot(th, r["T_dp"], color=_DP_LINE, lw=1.5, label="dew point")
    ax[2].set_ylabel("dew point [°C]")
    _dlo = min(float(np.min(r["T_dp"])), config.DP_ALLOW_LOW_C)
    _dhi = max(float(np.max(r["T_dp"])), config.DP_ALLOW_HIGH_C)
    _dpad = 0.05 * (_dhi - _dlo) + 0.5
    ax[2].set_ylim(_dlo - _dpad, _dhi + _dpad)
    ax[2].set_xlabel("time of day [h]"); ax[2].set_xlim(0, 24)
    ax[2].legend(loc="upper right", fontsize=8)

    # (4) operating mode (background shading -- NOT a step line, which just
    # smears black at realistic OFF/VENT/AC switching rates) + cooling powers
    for t0, t1 in _mode_spans(th, r["mode"], "AC"):
        ax[3].axvspan(t0, t1, color=_AC_SHADE, alpha=0.18, lw=0)
    for t0, t1 in _mode_spans(th, r["mode"], "VENT"):
        ax[3].axvspan(t0, t1, color=_VENT_SHADE, alpha=0.15, lw=0)
    ax[3].set_yticks([])
    axc = ax[3].twinx()
    axc.plot(th, r["Q_dem"], color=_LOAD_LINE, lw=1.2, label="server load")
    axc.plot(th, r["Q_cool"], color=_COOL_LINE, ls="--", lw=1.2, label="cooling delivered")
    axc.yaxis.tick_left(); axc.yaxis.set_label_position("left")
    axc.set_ylabel("power [kW]"); axc.set_ylim(0, max(8, r["Q_cool"].max() * 1.1))
    mode_handles = [Patch(facecolor=_AC_SHADE, alpha=0.18, label="AC"),
                    Patch(facecolor=_VENT_SHADE, alpha=0.15, label="VENT")]
    power_handles, power_labels = axc.get_legend_handles_labels()
    axc.legend(handles=mode_handles + power_handles, labels=["AC", "VENT"] + power_labels,
              loc="upper right", fontsize=8)
    ax[3].set_xlabel("time of day [h]"); ax[3].set_xlim(0, 24)

    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def plot_overview(R, path, label=None):
    """label: design description for the title, e.g. 'Propane, 30 mm' (the
    Task-3 selected design). Defaults to the Task-1 single-bore stand-in,
    matching plot_season's convention."""
    if label is None:
        label = "%g mm / %s stand-in" % (config.STANDIN_BORE_MM, config.STANDIN_REFRIGERANT)
    fig, ax = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    colors = config.SEASON_COLORS
    ax[0].axhspan(config.T_ALLOW_LOW_C, config.T_ALLOW_HIGH_C,
                  color=config.COLOR_RECOMMENDED_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g °C" % (config.T_ALLOW_LOW_C, config.T_ALLOW_HIGH_C))
    ax[0].axhspan(config.T_RECOMMENDED_LOW_C, config.T_RECOMMENDED_HIGH_C,
                  color=config.COLOR_RECOMMENDED_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="recommended %g-%g °C" % (config.T_RECOMMENDED_LOW_C, config.T_RECOMMENDED_HIGH_C))
    for s in config.SEASONS:
        th = R[s]["t"] / 60.0
        ax[0].plot(th, R[s]["T"], color=colors[s], lw=1.3, label=s)
        ax[1].plot(th, 100 * R[s]["phi"], color=colors[s], lw=1.3)   # colors shared with ax[0]'s legend
        ax[2].plot(th, R[s]["T_dp"], color=colors[s], lw=1.3)
    _allT = np.concatenate([R[s]["T"] for s in config.SEASONS])
    _tlo = min(float(_allT.min()), config.T_ALLOW_LOW_C)
    _thi = max(float(_allT.max()), config.T_ALLOW_HIGH_C)
    _pad = 0.05 * (_thi - _tlo) + 0.5
    ax[0].set_ylabel("room T [°C]"); ax[0].set_ylim(_tlo - _pad, _thi + _pad)
    ax[0].set_title("Four representative days - room temperature & humidity (%s)" % label)
    ax[0].legend(loc="upper right", ncol=3, fontsize=8)
    ax[1].axhspan(100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH,
                  color=config.COLOR_HUMIDITY_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g %%" % (100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH))
    ax[1].set_ylabel("room RH [%]"); ax[1].set_ylim(0, 90)
    ax[1].legend(loc="upper right", ncol=2, fontsize=8)
    # DP allowable is pinned to literally equal RH's allowable (same
    # purple-partner colour as ax[1]'s span above).
    ax[2].axhspan(config.DP_ALLOW_LOW_C, config.DP_ALLOW_HIGH_C,
                  color=config.COLOR_HUMIDITY_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="allowable %g-%g C" % (config.DP_ALLOW_LOW_C, config.DP_ALLOW_HIGH_C))
    ax[2].axhspan(config.DP_RECOMMENDED_LOW_C, config.DP_RECOMMENDED_HIGH_C,
                  color=config.COLOR_HUMIDITY_BAND, alpha=config.ALPHA_RECOMMENDED_BAND,
                  label="recommended %g-%g C" % (config.DP_RECOMMENDED_LOW_C, config.DP_RECOMMENDED_HIGH_C))
    _allDP = np.concatenate([R[s]["T_dp"] for s in config.SEASONS])
    _dlo = min(float(_allDP.min()), config.DP_ALLOW_LOW_C)
    _dhi = max(float(_allDP.max()), config.DP_ALLOW_HIGH_C)
    _dpad = 0.05 * (_dhi - _dlo) + 0.5
    ax[2].set_ylabel("dew point [°C]"); ax[2].set_ylim(_dlo - _dpad, _dhi + _dpad)
    ax[2].set_xlabel("time of day [h]"); ax[2].set_xlim(0, 24)
    ax[2].legend(loc="upper right", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=config.FIGURE_DPI); plt.close(fig)


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

    cmap = _TASK2_SEQUENTIAL_BY_VALUE.get(value, config.SEQUENTIAL_CMAP_COP)
    cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap)
    ax.contour(X, Y, Z, levels=levels, colors=config.COLOR_NEUTRAL, linewidths=0.3, alpha=0.5)
    if show_points:
        ax.scatter(X, Y, s=6, facecolors="none", edgecolors=config.COLOR_NEUTRAL, linewidths=0.4)

    ax.set_title(f"{refrigerant} — {D_bore:.0f} mm bore")
    if own_fig:
        ax.set_xlabel("$T_{room}$  [°C]   (source)")
        ax.set_ylabel("$T_{amb}$  [°C]   (sink)")
        plt.colorbar(cf, ax=ax).set_label(_MAP_LABELS.get(value, value))
        if save:
            fig.tight_layout()
            fig.savefig(f"perfmap_{refrigerant}_{D_bore:.0f}mm_{value}.png", dpi=config.FIGURE_DPI)
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
        fig.savefig(f"perfmap_grid_{value}.png", dpi=config.FIGURE_DPI, bbox_inches="tight")
    return fig


# --------------------------------------------------------------- Task 3 sweep
def plot_design_comparison_detailed(df_compare, path, best=None):
    """Six-panel breakdown of the Task-3 comparison table: duty-cycle split
    (AC/VENT/OFF minutes), energy split (compressor vs fan), start counts
    side by side, and the room temperature/humidity/dew-point excursion
    ranges. Designs are ordered by rank (best first) rather than
    alphabetically, so the trade-off reads left to right."""
    df = df_compare.sort_values("rank")
    labels = [f"{r}\n{b:.0f} mm" for r, b in zip(df["refrigerant"], df["bore_mm"])]
    is_best = [(r, b) == best for r, b in zip(df["refrigerant"], df["bore_mm"])]
    edge = [config.COLOR_SELECTED_DESIGN if b else "none" for b in is_best]
    x = np.arange(len(df))
    w = 0.6

    def outline_bars(a, top, bottom=0.0):
        """Tight outline around the selected design's bar(s), instead
        of a translucent column spanning the whole axis (looked like a stray
        highlight strip when the bar itself was much shorter)."""
        bottom = np.broadcast_to(np.asarray(bottom, dtype=float), np.shape(top))
        for xi, e, t, b in zip(x, edge, top, bottom):
            if e != "none":
                a.add_patch(Rectangle((xi - w / 2, b), w, t - b, fill=False,
                                       edgecolor=config.COLOR_SELECTED_DESIGN, linewidth=2, zorder=5))

    fig, ax = plt.subplots(2, 3, figsize=(max(13, 3.0 * len(df)), 7.5))

    # (1) duty-cycle minutes, stacked
    a = ax[0, 0]
    a.bar(x, df["ac_min_total"], w, color=config.COLOR_AC, label="AC")
    a.bar(x, df["vent_min_total"], w, bottom=df["ac_min_total"], color=config.COLOR_VENT, label="VENT")
    a.bar(x, df["off_min_total"], w,
          bottom=df["ac_min_total"] + df["vent_min_total"], color=config.COLOR_OFF, alpha=0.5, label="OFF")
    outline_bars(a, df["ac_min_total"] + df["vent_min_total"] + df["off_min_total"])
    a.set_ylabel("operating time [min / 4 days]")
    a.set_title("Duty cycle"); a.legend(fontsize=8, loc="upper right")

    # (2) energy split, stacked
    a = ax[0, 1]
    a.bar(x, df["E_ac_kWh"], w, color=config.COLOR_AC, label="compressor")
    a.bar(x, df["E_vent_kWh"], w, bottom=df["E_ac_kWh"], color=config.COLOR_VENT, label="fan")
    outline_bars(a, df["E_ac_kWh"] + df["E_vent_kWh"])
    a.set_ylabel("electrical energy [kWh / 4 days]")
    a.set_title("Energy split"); a.legend(fontsize=8, loc="upper right")

    # (3) start counts, grouped
    a = ax[0, 2]
    a.bar(x - w / 4, df["ac_starts_total"], w / 2, color=config.COLOR_AC, label="AC starts")
    a.bar(x + w / 4, df["vent_starts_total"], w / 2, color=config.COLOR_VENT, label="VENT starts")
    outline_bars(a, np.maximum(df["ac_starts_total"], df["vent_starts_total"]))
    a.set_ylabel("cycle starts [4 days]")
    a.set_title("Switching frequency"); a.legend(fontsize=8, loc="upper right")

    # (4) room humidity range (phi_min - phi_max) per design -- allowable only
    a = ax[1, 0]
    a.axhspan(100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH,
              color=config.COLOR_HUMIDITY_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND, label="allowable")
    lo, hi = 100 * df["phi_min"], 100 * df["phi_max"]
    a.bar(x, hi - lo, w, bottom=lo, color=config.COLOR_ROOM_RH)
    outline_bars(a, hi, lo)
    a.set_ylabel("room RH range [%]")
    a.set_title("Humidity excursion"); a.legend(fontsize=8, loc="upper right")

    # (5) dew point range (dp_min - dp_max) per design -- same pink/purple as
    # the room RH bar (4), tying the two humidity-family panels together
    a = ax[1, 1]
    a.axhspan(config.DP_ALLOW_LOW_C, config.DP_ALLOW_HIGH_C,
              color=config.COLOR_HUMIDITY_BAND_ALLOWABLE, alpha=config.ALPHA_RECOMMENDED_BAND, label="allowable")
    a.axhspan(config.DP_RECOMMENDED_LOW_C, config.DP_RECOMMENDED_HIGH_C,
              color=config.COLOR_HUMIDITY_BAND, alpha=config.ALPHA_RECOMMENDED_BAND, label="recommended")
    lo, hi = df["dp_min"], df["dp_max"]
    a.bar(x, hi - lo, w, bottom=lo, color=config.COLOR_ROOM_RH)
    outline_bars(a, hi, lo)
    a.set_ylabel("dew point range [°C]")
    a.set_title("Dew point excursion"); a.legend(fontsize=8, loc="upper right")

    # (6) time within the T band, recommended vs allowable -- green, matching
    # the T band/colour scheme used in the one-day plots (plot_season).
    # Paired bars (full colour = recommended, faded = allowable) read the
    # trade-off more directly than the raw T_min-T_max excursion range did.
    a = ax[1, 2]
    a.bar(x - w / 4, 100 * df["frac_T_recommended"], w / 2,
          color=config.COLOR_RECOMMENDED_BAND, label="recommended")
    a.bar(x + w / 4, 100 * df["frac_T_allowable"], w / 2,
          color=config.COLOR_RECOMMENDED_BAND, alpha=0.45, label="allowable")
    outline_bars(a, np.full(len(x), 100.0))
    a.axhline(100, color=config.COLOR_NEUTRAL, ls=":", lw=0.9)
    a.set_ylabel("time in T band [%]")
    a.set_title("Temperature compliance"); a.legend(fontsize=8, loc="upper right")

    for a in ax.flat:
        a.set_xticks(x); a.set_xticklabels(labels, fontsize=8)
    fig.suptitle("Task 3 design comparison, detail (gold outline = selected, "
                 "ordered by rank)")
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def plot_design_comparison(df_compare, path, best=None):
    """Bar charts of the Task-3 selection criteria across all (refrigerant,
    bore) combinations: room T compliance (recommended/allowable), room RH
    compliance (allowable only -- no recommended target), dew point
    compliance (recommended/allowable), total electrical energy, and AC
    compressor start count. `best` = (refrigerant, bore_mm) to highlight
    (orange outline); df_compare has one row per combo (see task3.sweep)."""
    df = df_compare.sort_values(["refrigerant", "bore_mm"])
    labels = [f"{r}\n{b:.0f} mm" for r, b in zip(df["refrigerant"], df["bore_mm"])]
    is_best = [(r, b) == best for r, b in zip(df["refrigerant"], df["bore_mm"])]
    x = np.arange(len(df))
    w = 0.35

    def outline_best(a, top):
        top = np.broadcast_to(np.asarray(top, dtype=float), x.shape)
        for xi, b, t in zip(x, is_best, top):
            if b:
                a.add_patch(Rectangle((xi - 0.5, 0), 1.0, t, fill=False,
                                       edgecolor=config.COLOR_SELECTED_DESIGN, linewidth=2, zorder=5))

    fig, ax = plt.subplots(5, 1, figsize=(max(7, 1.3 * len(df)), 13), sharex=True)

    ax[0].bar(x - w / 2, 100 * df["frac_T_recommended"], w, color=config.COLOR_ROOM_T, label="recommended")
    ax[0].bar(x + w / 2, 100 * df["frac_T_allowable"], w, color=config.COLOR_ROOM_T_ALLOWABLE, label="allowable")
    outline_best(ax[0], 100)
    ax[0].axhline(100, color=config.COLOR_NEUTRAL, ls=":", lw=0.9)
    ax[0].set_ylabel("time in T band [%]")
    ax[0].set_title("Task 3 design comparison (gold outline = selected)")
    ax[0].legend(fontsize=8)

    # RH: allowable only -- no separate recommended target, so one bar per design
    ax[1].bar(x, 100 * df["frac_phi_allowable"], 2 * w / 3, color=config.COLOR_ROOM_RH, label="allowable")
    outline_best(ax[1], 100)
    ax[1].axhline(100, color=config.COLOR_NEUTRAL, ls=":", lw=0.9)
    ax[1].set_ylabel("time in RH band [%]")
    ax[1].legend(fontsize=8)

    ax[2].bar(x - w / 2, 100 * df["frac_dp_recommended"], w, color=config.COLOR_DEW_POINT, label="recommended")
    ax[2].bar(x + w / 2, 100 * df["frac_dp_allowable"], w, color=config.COLOR_DEW_POINT_ALLOWABLE, label="allowable")
    outline_best(ax[2], 100)
    ax[2].axhline(100, color=config.COLOR_NEUTRAL, ls=":", lw=0.9)
    ax[2].set_ylabel("time in DP band [%]")
    ax[2].legend(fontsize=8)

    ax[3].bar(x, df["E_total_kWh"], color=config.COLOR_AC)
    outline_best(ax[3], df["E_total_kWh"])
    ax[3].set_ylabel("total electrical\nenergy [kWh / 4 days]")

    ax[4].bar(x, df["ac_starts_total"], color=config.COLOR_AC)
    outline_best(ax[4], df["ac_starts_total"])
    ax[4].set_ylabel("AC compressor\nstarts [4 days]")
    ax[4].set_xticks(x); ax[4].set_xticklabels(labels, fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)


def plot_cost_comparison(df_cost, path, best=None, dates=None):
    """Task 4: stacked electricity cost over the 4 representative days (AC +
    ventilation) per (refrigerant, bore) design, costed against REAL day-ahead
    prices (task4.economics). `best` = (refrigerant, bore_mm) to highlight
    (gold outline); df_cost has one row per combo. `dates` = {season: "DD/
    MM/YYYY"} (data_io.load_dayahead_prices) -- shown in the subtitle so the
    figure is traceable to the exact price data it used."""
    df = df_cost.sort_values(["refrigerant", "bore_mm"])
    labels = [f"{r}\n{b:.0f} mm" for r, b in zip(df["refrigerant"], df["bore_mm"])]
    is_best = [(r, b) == best for r, b in zip(df["refrigerant"], df["bore_mm"])]
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(max(7, 1.1 * len(df)), 5))
    ax.bar(x, df["cost_ac_CHF"], color=config.COLOR_AC, label="AC")
    ax.bar(x, df["cost_vent_CHF"], bottom=df["cost_ac_CHF"],
          color=config.COLOR_VENT, label="ventilation")

    top = df["cost_total_CHF"].to_numpy(dtype=float)
    for xi, b, t in zip(x, is_best, top):
        if b:
            ax.add_patch(Rectangle((xi - 0.5, 0), 1.0, t, fill=False,
                                   edgecolor=config.COLOR_SELECTED_DESIGN, linewidth=2, zorder=5))

    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("electricity cost  [CHF / 4 representative days]")
    title = "Task 4 design comparison (gold outline = Task-3 selection)"
    if dates:
        seasons = [s for s in config.SEASONS if s in dates]
        line1 = ", ".join("%s %s" % (s, dates[s]) for s in seasons[:2])
        line2 = ", ".join("%s %s" % (s, dates[s]) for s in seasons[2:])
        title += "\nday-ahead prices: %s, %s" % (line1, line2)
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)


def plot_dayahead_prices(prices_by_season, path):
    """Task 4: the real hourly day-ahead price curve used for each
    representative season (common.data_io.load_dayahead_prices). Each
    season's exact calendar date is in the legend, so the figure is
    self-documenting about which real day it's costing against."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for season in config.SEASONS:
        d = prices_by_season[season]
        ax.step(range(24), d["price_chf_per_kwh"], where="post",
                color=config.SEASON_COLORS[season], lw=1.5,
                label="%s (%s)" % (season, d["date"]))
    ax.set_xlabel("hour of day [h]"); ax.set_ylabel("day-ahead price  [CHF/kWh]")
    ax.set_xlim(0, 23); ax.set_xticks(range(0, 24, 2))
    ax.set_title("Real day-ahead electricity prices (ENTSO-E, BZN|CH)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=config.FIGURE_DPI)
    plt.close(fig)
