"""
Inner COP optimisation in the course's Lecture-3 / Exercise-3 standard form.

Exercise 3 optimises the DECISION VARIABLES [T_co, T_ev] (minimising 1/COP with
scipy SLSQP) while superheat and subcooling are GIVEN CONSTANTS and the approach
temperatures are MINIMUM-pinch inequality constraints. Because COP is monotone
(increasing in T_ev, decreasing in T_co) the optimum sits on the tightest
approach constraint  ->  T_ev* = T_room - EVAP,  T_co* = T_amb + COND. That is
exactly the constant-approach cycle in cycle.py, so the time simulation uses the
precomputed map (Hint 1) and never calls an optimiser. This module is the
offline standard-form statement + verification for the report.

Standard form (per timestep, given T_room, T_amb, bore, refrigerant):
    decision variables : T_co, T_ev                        [degC]
    constants (w)       : dT_sh, dT_sc, bore, refrigerant, T_room, T_amb
    objective           : max COP = q_evap / w_comp        (=> min 1/COP)
    constraints         : T_room - T_ev >= EVAP            (evaporator approach floor)
                          T_co  - T_amb >= COND            (condenser approach floor)
                          p_co / p_ev   >= MIN_PRESSURE_RATIO
                          T_amb < T_co < T_crit ,  T_ev < T_room   (bounds; subcritical)

Difference vs Ex.3: Ex.3 resolves the pinch at every HX location, which needs the
source/sink GLIDES (secondary-fluid flows). We do not have the air flows, so the
per-location pinch is replaced by one lumped approach floor per HX, and the
min-pressure-ratio envelope (absent in Ex.3) is added.
"""
import os
import sys
if __name__ == "__main__":
    # Self-bootstrap (script run directly, e.g. `python src/task2/cycle_opt.py`):
    # add src/ to sys.path and cwd to the repo root, same pattern as analysis/*.py.
    # Must run BEFORE the `from common import ...` below, and BEFORE any other
    # module-level code -- a __main__ guard at the bottom of the file is too
    # late, since Python executes this file top-to-bottom on direct run. Guarded
    # so importing this module normally (`from task2 import cycle_opt`) is
    # unaffected (no sys.path/cwd mutation on import).
    _REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, os.path.join(_REPO, "src"))
    os.chdir(_REPO)

import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless: write a PNG, do not require a display
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
from scipy.optimize import minimize, NonlinearConstraint
from common import config, Fluid_CP as FCP, compressor_model as comp

EH = "CBar"


def _states(T_co, T_ev, refrigerant, dt_sh, dt_sc, bore_mm):
    """Cycle states at given temperatures. Returns (p_ev, p_co, q_evap, w_comp,
    eta_is, m_dot) in course units (bar, kJ/kg, kg/s)."""
    sat_ev = FCP.state(["T", "x"], [T_ev, 1.0], refrigerant, Eh=EH)
    sat_co = FCP.state(["T", "x"], [T_co, 1.0], refrigerant, Eh=EH)
    p_ev, p_co = sat_ev["p"], sat_co["p"]
    z1 = FCP.state(["T", "p"], [T_ev + dt_sh, p_ev], refrigerant, Eh=EH)   # suction
    z2s = FCP.state(["p", "s"], [p_co, z1["s"]], refrigerant, Eh=EH)        # isentropic
    eta_is, m_dot = comp.recip_comp_corr_SP(
        (T_ev, T_co, dt_sh, dt_sc, bore_mm), refrigerant)
    h2 = z1["h"] + (z2s["h"] - z1["h"]) / eta_is
    if dt_sc > 0.0:
        z3 = FCP.state(["T", "p"], [T_co - dt_sc, p_co], refrigerant, Eh=EH)    # subcooled liquid
    else:
        # dt_sc = 0 sits exactly on the saturation line; (T, p) there is the
        # degenerate two-phase boundary and CoolProp errors (see cycle.cycle_point's
        # same guard). Use the robust (T, x=0) saturated-liquid entry instead.
        z3 = FCP.state(["T", "x"], [T_co, 0.0], refrigerant, Eh=EH)
    q_evap = z1["h"] - z3["h"]      # h1 - h4 (isenthalpic throttle, h4 = h3)
    w_comp = h2 - z1["h"]
    return p_ev, p_co, q_evap, w_comp, eta_is, m_dot


def _inv_cop(param, T_room, T_amb, bore_mm, refrigerant, dt_sh, dt_sc):
    """Objective for minimize: 1 / COP_cooling at param = [T_co, T_ev]."""
    T_co, T_ev = param
    _, _, q_evap, w_comp, _, _ = _states(T_co, T_ev, refrigerant, dt_sh, dt_sc, bore_mm)
    return w_comp / q_evap


def _approaches(param, T_room, T_amb):
    T_co, T_ev = param
    return [T_room - T_ev, T_co - T_amb]      # [evap approach, cond approach]


def _pratio(param, refrigerant):
    T_co, T_ev = param
    p_ev = FCP.state(["T", "x"], [T_ev, 1.0], refrigerant, Eh=EH)["p"]
    p_co = FCP.state(["T", "x"], [T_co, 1.0], refrigerant, Eh=EH)["p"]
    return p_co / p_ev


def optimize_cop(T_room, T_amb, bore_mm=None, refrigerant=None, dt_sh=None, dt_sc=None):
    """Solve the Ex.3-style inner optimisation; return optimal cycle temps + COP."""
    bore_mm = config.STANDIN_BORE_MM if bore_mm is None else bore_mm
    refrigerant = config.STANDIN_REFRIGERANT if refrigerant is None else refrigerant
    dt_sh = config.DELTA_T_SUPERHEAT_K if dt_sh is None else dt_sh
    dt_sc = config.DELTA_T_SUBCOOL_K if dt_sc is None else dt_sc

    T_crit = FCP.get_fluid_info(refrigerant, EH)["T_crit"]
    bounds = [(T_amb, T_crit - 1.0), (-40.0, T_room - 0.01)]       # (T_co, T_ev)

    NC_app = NonlinearConstraint(
        lambda p: _approaches(p, T_room, T_amb),
        [config.DT_APPROACH_EVAP_K, config.DT_APPROACH_COND_K], [np.inf, np.inf])
    NC_pi = NonlinearConstraint(
        lambda p: _pratio(p, refrigerant), config.MIN_PRESSURE_RATIO, np.inf)

    x0 = [T_amb + config.DT_APPROACH_COND_K, T_room - config.DT_APPROACH_EVAP_K]
    res = minimize(_inv_cop, x0=x0,
                   args=(T_room, T_amb, bore_mm, refrigerant, dt_sh, dt_sc),
                   method="SLSQP", bounds=bounds, constraints=(NC_app, NC_pi),
                   options={"ftol": 1e-9, "maxiter": 200})

    T_co_op, T_ev_op = res.x
    p_ev, p_co, q_evap, w_comp, eta_is, m_dot = _states(
        T_co_op, T_ev_op, refrigerant, dt_sh, dt_sc, bore_mm)
    return {
        "success": bool(res.success), "COP": 1.0 / res.fun,
        "T_ev": T_ev_op, "T_co": T_co_op,
        "approach_evap": T_room - T_ev_op, "approach_cond": T_co_op - T_amb,
        "p_ratio": p_co / p_ev, "Q_AC_kW": m_dot * q_evap,
    }


def pinch_check_grid(T_room_grid, T_amb_grid, bore_mm=None, refrigerant=None, tol_K=0.05):
    """Run optimize_cop at every (T_room, T_amb) grid point and compare the
    SLSQP optimum against the pinch-floor prediction
        T_ev* = T_room - DT_APPROACH_EVAP_K,   T_co* = T_amb + DT_APPROACH_COND_K
    i.e. the constant-approach cycle cycle.cycle_point() already uses. Returns a
    dict of (len(T_room_grid), len(T_amb_grid)) arrays. "at_floor" is False
    where the MIN_PRESSURE_RATIO constraint binds INSTEAD of the two approach
    floors (the low-lift "Pi_min clamp" regime, see cycle.py's docstring) --
    there the floor prediction is no longer exactly the optimum."""
    from task2 import cycle   # local import: cycle.py does not import cycle_opt
    nR, nA = len(T_room_grid), len(T_amb_grid)
    T_ev_opt = np.zeros((nR, nA)); T_co_opt = np.zeros((nR, nA))
    COP_opt = np.zeros((nR, nA)); COP_cp = np.zeros((nR, nA))
    p_ratio = np.zeros((nR, nA)); at_floor = np.zeros((nR, nA), dtype=bool)
    for i, tr in enumerate(T_room_grid):
        for j, ta in enumerate(T_amb_grid):
            o = optimize_cop(tr, ta, bore_mm, refrigerant)
            c = cycle.cycle_point(tr, ta, bore_mm, refrigerant)
            T_ev_opt[i, j], T_co_opt[i, j] = o["T_ev"], o["T_co"]
            COP_opt[i, j], COP_cp[i, j] = o["COP"], c["COP_inner"]
            p_ratio[i, j] = o["p_ratio"]
            ev_floor, co_floor = tr - config.DT_APPROACH_EVAP_K, ta + config.DT_APPROACH_COND_K
            at_floor[i, j] = (abs(o["T_ev"] - ev_floor) < tol_K and
                              abs(o["T_co"] - co_floor) < tol_K)
        print("  ... T_room=%.0f row done" % tr)
    return {"T_room_grid": T_room_grid, "T_amb_grid": T_amb_grid,
            "T_ev_opt": T_ev_opt, "T_co_opt": T_co_opt,
            "COP_opt": COP_opt, "COP_cyclepoint": COP_cp,
            "p_ratio_opt": p_ratio, "at_floor": at_floor}


def save_pinch_grid(grid, path):
    """Cache a pinch_check_grid() result to .npz -- the SLSQP sweep is the slow
    part (minutes); this lets plot_pinch_check() be restyled/iterated on for
    free afterwards, without re-running the optimizer."""
    np.savez(path, **grid)


def load_pinch_grid(path):
    """Inverse of save_pinch_grid(). Returns the same dict shape as
    pinch_check_grid()."""
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


_OKABE_ITO_DIVERGING = LinearSegmentedColormap.from_list(
    "okabe_ito_diverging", [config.OKABE_BLUE, "white", config.OKABE_VERMILLION])


def plot_pinch_check(grid, path):
    """3-panel figure over the (T_amb, T_room) plane: how far the SLSQP optimum's
    T_ev/T_co sit from the pinch-floor prediction, and the resulting COP gap
    against cycle.cycle_point. Deviation should be ~0 everywhere except where
    the hatched region marks the compressor's minimum pressure-ratio envelope
    (p_co/p_ev >= MIN_PRESSURE_RATIO) binding instead of the two approach floors."""
    Tr, Ta = grid["T_room_grid"], grid["T_amb_grid"]
    dEv = grid["T_ev_opt"] - (Tr[:, None] - config.DT_APPROACH_EVAP_K)
    dCo = grid["T_co_opt"] - (Ta[None, :] + config.DT_APPROACH_COND_K)
    dCOP = grid["COP_opt"] - grid["COP_cyclepoint"]
    at_floor = grid["at_floor"].astype(float)

    plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "figure.facecolor": "white",
                         "hatch.color": "0.3"})
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
    panels = [(dEv, "(a)  optimal T_ev shift  [K]"),
              (dCo, "(b)  optimal T_co shift  [K]"),
              (dCOP, "(c)  COP gap  [–]")]
    # Explicit Rectangle per clamped cell, edges computed from the same grid
    # pcolormesh(shading="nearest") uses internally -- guarantees both correct
    # alignment (no contourf-style interpolation gaps at the domain edges) and
    # reliable hatch rendering (QuadMesh/pcolormesh hatch-on-transparent-face
    # silently fails to draw on this matplotlib/backend combo; Rectangle
    # patches render hatches reliably).
    def _cell_edges(centers):
        c = np.asarray(centers, dtype=float)
        mid = (c[:-1] + c[1:]) / 2.0
        return np.concatenate([[c[0] - (mid[0] - c[0])], mid, [c[-1] + (c[-1] - mid[-1])]])
    ta_edges, tr_edges = _cell_edges(Ta), _cell_edges(Tr)
    clamped_ij = np.argwhere(~grid["at_floor"].astype(bool))

    for a, (data, title) in zip(ax, panels):
        vmax = max(float(np.max(np.abs(data))), 1e-6)
        im = a.pcolormesh(Ta, Tr, data, shading="nearest", cmap=_OKABE_ITO_DIVERGING,
                          vmin=-vmax, vmax=vmax, edgecolors="0.85", linewidth=0.4)
        for i, j in clamped_ij:
            a.add_patch(Rectangle((ta_edges[j], tr_edges[i]),
                                  ta_edges[j + 1] - ta_edges[j], tr_edges[i + 1] - tr_edges[i],
                                  facecolor="none", edgecolor="0.3", linewidth=0.0,
                                  hatch="//", zorder=3))
        a.set_xlabel("$T_{amb}$  [°C]"); a.set_ylabel("$T_{room}$  [°C]")
        a.set_title(title)
        fig.colorbar(im, ax=a, shrink=0.9)

    worst = np.unravel_index(np.argmax(dCOP), dCOP.shape)
    ax[2].plot(Ta[worst[1]], Tr[worst[0]], marker="*", color="black",
              markersize=15, markeredgecolor="white", markeredgewidth=1.0, zorder=6)
    ax[2].annotate("worst case\n+%.2f (%.0f%%)" % (dCOP[worst], 100*dCOP[worst]/grid["COP_cyclepoint"][worst]),
                   (Ta[worst[1]], Tr[worst[0]]), textcoords="offset points",
                   xytext=(10, -16), fontsize=9, fontweight="bold",
                   bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                            edgecolor="0.3", alpha=0.9), zorder=7)

    hatch_proxy = Patch(facecolor="white", edgecolor="0.3", hatch="//",
                        label="min. pressure-ratio limit active (floor prediction breaks down)")
    fig.legend(handles=[hatch_proxy], loc="lower center", bbox_to_anchor=(0.5, -0.06),
              frameon=False, fontsize=10)
    fig.suptitle("Optimizer vs. constant-approach cycle", fontsize=13)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    return fig


def pinch_check_all_combos(T_room_grid, T_amb_grid):
    """Same comparison as pinch_check_grid, summarised across every (refrigerant,
    bore) combo Task 2 actually builds a map for -- quantifies how much COP the
    production map (cycle.build_map, which uses cycle_point) leaves on the table
    vs the true SLSQP optimum, system-wide rather than just the stand-in combo.
    Returns the list of per-combo summary dicts (also printed as they're computed,
    since each combo's grid takes a couple of minutes)."""
    rows = []
    for refrigerant in config.REFRIGERANTS:
        for bore in config.COMPRESSOR_BORES_MM:
            grid = pinch_check_grid(T_room_grid, T_amb_grid, bore_mm=bore, refrigerant=refrigerant)
            dCOP = grid["COP_opt"] - grid["COP_cyclepoint"]
            with np.errstate(invalid="ignore", divide="ignore"):
                pct = 100.0 * dCOP / grid["COP_cyclepoint"]
            n_total = grid["at_floor"].size
            n_clamped = n_total - int(grid["at_floor"].sum())
            worst = np.unravel_index(np.argmax(dCOP), dCOP.shape)
            row = {"refrigerant": refrigerant, "bore_mm": bore,
                   "n_clamped": n_clamped, "n_total": n_total,
                   "mean_COP_gap_pct": float(np.nanmean(pct)),
                   "max_COP_gap_pct": float(pct[worst]),
                   "worst_T_room": float(T_room_grid[worst[0]]),
                   "worst_T_amb": float(T_amb_grid[worst[1]])}
            rows.append(row)
            print("  %-14s %4.0fmm: %d/%d clamped, mean gap %+.2f%%, max gap %+.2f%% "
                  "@ T_room=%.0f T_amb=%.0f"
                  % (refrigerant, bore, n_clamped, n_total, row["mean_COP_gap_pct"],
                     row["max_COP_gap_pct"], row["worst_T_room"], row["worst_T_amb"]))
    return rows


def main(all_combos=False, from_cache=None):
    from task2 import cycle

    # Restyle-only path: skip the optimizer entirely and re-plot from a
    # previously cached grid (see save_pinch_grid below).
    if from_cache:
        grid = load_pinch_grid(from_cache)
        os.makedirs("figures", exist_ok=True)
        path = os.path.join("figures", "task2_pinch_optimality.png")
        plot_pinch_check(grid, path)
        print("Figure re-rendered from %s -> %s" % (from_cache, path))
        return

    # (1) Spot check across all three refrigerants: the SLSQP optimum must
    # reproduce the constant-approach cycle (or, where Pi_min binds, come close).
    hdr = "  point                       opt-COP  appr_ev appr_co p_ratio  ok |  map-COP  clamp"
    print(hdr)
    for T_room, T_amb in [(15, 30), (22, 35), (15, 2)]:
        for refrigerant in config.REFRIGERANTS:
            o = optimize_cop(T_room, T_amb, refrigerant=refrigerant)
            c = cycle.cycle_point(T_room, T_amb, refrigerant=refrigerant)
            match = abs(o["COP"] - c["COP_inner"]) < 0.02
            print("  T_room=%2d T_amb=%2d %-14s  %.3f   %5.1f   %5.1f   %.2f  %s |  %.3f   %s"
                  % (T_room, T_amb, refrigerant, o["COP"], o["approach_evap"],
                     o["approach_cond"], o["p_ratio"], "Y" if match else "N",
                     c["COP_inner"], c["clamped"]))

    # (2) Grid sweep, stand-in (bore, refrigerant): map out WHERE the floor
    # prediction holds vs where Pi_min takes over. Each point is a fresh SLSQP
    # solve (~1-10 s); this loop takes a few minutes.
    print("\nGrid sweep (%.0f mm / %s) -- calls the SLSQP optimizer at every point, "
          "this takes a few minutes..." % (config.STANDIN_BORE_MM, config.STANDIN_REFRIGERANT))
    T_room_grid = np.arange(15.0, 31.0, 5.0)
    T_amb_grid = np.arange(0.0, 36.0, 5.0)
    grid = pinch_check_grid(T_room_grid, T_amb_grid)

    n_total = grid["at_floor"].size
    n_floor = int(grid["at_floor"].sum())
    dCOP = grid["COP_opt"] - grid["COP_cyclepoint"]
    print("\n%d/%d grid points: optimum sits exactly AT the pinch floor "
          "(T_ev*=T_room-EVAP, T_co*=T_amb+COND)." % (n_floor, n_total))
    print("%d/%d points: the MIN_PRESSURE_RATIO constraint binds instead -- the floor "
          "prediction is no longer the optimum there." % (n_total - n_floor, n_total))
    if n_total - n_floor:
        worst = np.unravel_index(np.argmax(np.abs(dCOP)), dCOP.shape)
        print("  worst case: T_room=%.0f T_amb=%.0f -> COP gap %.3f (optimizer %.3f vs "
              "cycle_point %.3f, %.1f%% higher)"
              % (T_room_grid[worst[0]], T_amb_grid[worst[1]], dCOP[worst],
                 grid["COP_opt"][worst], grid["COP_cyclepoint"][worst],
                 100.0 * dCOP[worst] / grid["COP_cyclepoint"][worst]))

    os.makedirs("figures", exist_ok=True)
    cache_path = os.path.join("figures", "task2_pinch_grid_cache.npz")
    save_pinch_grid(grid, cache_path)
    print("Grid data cached to %s (restyle the figure later with --from-cache, no "
          "need to re-run the optimizer)" % cache_path)

    path = os.path.join("figures", "task2_pinch_optimality.png")
    plot_pinch_check(grid, path)
    print("Figure written to %s" % path)

    # (3) Optional: same comparison summarised across every (refrigerant, bore)
    # combo Task 2 actually builds a map for, not just the stand-in. Coarser grid
    # (3x3 instead of 4x8) since this multiplies the cost by 9 combos.
    if all_combos:
        print("\n" + "=" * 78)
        print("All (refrigerant, bore) combos -- coarse 3x3 grid, ~5-7 min total")
        print("=" * 78)
        rows = pinch_check_all_combos(np.array([15.0, 22.0, 30.0]), np.array([0.0, 15.0, 30.0]))
        worst_row = max(rows, key=lambda r: r["max_COP_gap_pct"])
        print("\nWorst combo overall: %s %.0fmm, max COP gap %+.2f%% @ T_room=%.0f T_amb=%.0f"
              % (worst_row["refrigerant"], worst_row["bore_mm"], worst_row["max_COP_gap_pct"],
                 worst_row["worst_T_room"], worst_row["worst_T_amb"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-combos", action="store_true",
                        help="also summarise the COP gap across every (refrigerant, bore) "
                             "combo Task 2 builds a map for (coarse grid, ~5-7 min extra)")
    parser.add_argument("--from-cache", metavar="NPZ_PATH", default=None,
                        help="skip the optimizer entirely and re-render the figure from a "
                             "previously cached grid (figures/task2_pinch_grid_cache.npz)")
    args = parser.parse_args()
    main(all_combos=args.all_combos, from_cache=args.from_cache)
