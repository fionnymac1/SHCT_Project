"""
Subcritical vapour-compression cycle - Task-1 stand-in (one bore + refrigerant),
generalised over (bore, refrigerant) in Task 3.

Per Hint 1: the cycle is not re-solved every timestep -- COP_inner and capacity
Q_AC are precomputed on a (T_room, T_amb) grid and interpolated during the
simulation.

Cycle (constant approaches, also off-design): T_ev = T_room - DT_APPROACH_EVAP_K,
T_co = T_amb + DT_APPROACH_COND_K. 1: suction = sat. vapour at T_ev + superheat;
2: discharge = isentropic to p_co, corrected by eta_is; 3: condenser outlet =
sat. liquid at T_co (minus subcooling); 4: isenthalpic expansion (h4 = h3).
q_evap = h1-h4, w_comp = h2-h1, COP_inner = q_evap/w_comp, Q_AC = m_dot*q_evap.

Minimum-pressure-ratio envelope (p_co/p_ev >= MIN_PRESSURE_RATIO): at low lift
the natural ratio falls below the limit, so the condenser pressure is clamped
up to MIN_PRESSURE_RATIO * p_ev (a COP penalty, not an uncooled gap).

Superheat/subcooling are fixed, not optimised per point -- justified in
analysis/superheat_subcool_sweep.py (COP_inner is monotone in subcool, so the
map deliberately stays conservative of the sink bound; it's nearly flat and
fluid-dependent in sign for superheat, so the dry-suction minimum is used) and
checked against the true per-point optimum in analysis/cop_optimum.py (the
pinch floors are the binding constraint almost everywhere).

States via the course wrapper Fluid_CP.state (Eh='CBar' -> degC, bar, kJ/kg).
"""
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from common import config, Fluid_CP as FCP, compressor_model as comp

EH = "CBar"


def cycle_point(T_room_C, T_amb_C, bore_mm=None, refrigerant=None,
                dt_sh=None, dt_sc=None, T_ev_C=None, T_co_C=None):
    """One steady operating point. Returns a dict of cycle results.
       Accepts optional T_ev_C and T_co_C overrides for optimization."""
    bore_mm = config.STANDIN_BORE_MM if bore_mm is None else bore_mm
    refrigerant = config.STANDIN_REFRIGERANT if refrigerant is None else refrigerant
    dt_sh = config.DELTA_T_SUPERHEAT_K if dt_sh is None else dt_sh
    dt_sc = config.DELTA_T_SUBCOOL_K if dt_sc is None else dt_sc

    # ---------------------------------------------------------
    # RESOLVE TEMPERATURES (Override vs. Config Fallback)
    # ---------------------------------------------------------
    T_ev = T_ev_C if T_ev_C is not None else (T_room_C - config.DT_APPROACH_EVAP_K)
    T_co = T_co_C if T_co_C is not None else (T_amb_C + config.DT_APPROACH_COND_K)

    sat_ev = FCP.state(["T", "x"], [T_ev, 1.0], refrigerant, Eh=EH)
    sat_co = FCP.state(["T", "x"], [T_co, 1.0], refrigerant, Eh=EH)
    p_ev = sat_ev["p"]
    p_co = sat_co["p"]

    # minimum-pressure-ratio envelope: clamp condenser pressure / temperature up
    clamped = False
    if p_co < config.MIN_PRESSURE_RATIO * p_ev:
        p_co = config.MIN_PRESSURE_RATIO * p_ev
        T_co = FCP.state(["p", "x"], [p_co, 1.0], refrigerant, Eh=EH)["T"]
        clamped = True
    p_ratio = p_co / p_ev

    # 1 suction (superheated), 2s isentropic discharge
    z1 = FCP.state(["T", "p"], [T_ev + dt_sh, p_ev], refrigerant, Eh=EH)
    z2s = FCP.state(["p", "s"], [p_co, z1["s"]], refrigerant, Eh=EH)

    # compressor: (eta_is, m_dot[kg/s]); 4th slot (subcool) is ignored by the fn
    eta_is, m_dot = comp.recip_comp_corr_SP(
        (T_ev, T_co, dt_sh, dt_sc, bore_mm), refrigerant)

    h1, h2s = z1["h"], z2s["h"]
    h2 = h1 + (h2s - h1) / eta_is
    T_dis = FCP.state(["p", "h"], [p_co, h2], refrigerant, Eh=EH)["T"]  # actual discharge temp

    if dt_sc > 0.0:
        z3 = FCP.state(["T", "p"], [T_co - dt_sc, p_co], refrigerant, Eh=EH)
    else:
        z3 = FCP.state(["T", "x"], [T_co, 0.0], refrigerant, Eh=EH)
    h4 = z3["h"]

    q_evap = h1 - h4
    w_comp = h2 - h1
    Q_AC = m_dot * q_evap
    W = m_dot * w_comp
    cop = q_evap / w_comp

    return {
        "T_ev": T_ev, "T_co": T_co, "p_ev": p_ev, "p_co": p_co,
        "p_ratio": p_ratio, "clamped": clamped,
        "eta_is": eta_is, "m_dot": m_dot,
        "q_evap": q_evap, "w_comp": w_comp,
        "Q_AC_kW": Q_AC, "W_kW": W, "COP_inner": cop, "T_dis": T_dis,
        "T_AC": T_ev + config.DT_APPROACH_AIR_K,
        "dt_sc_actual": dt_sc
    }


def default_grids():
    """The (T_room, T_amb) grid main_task2.py sizes its maps on: T_amb spans the
    four season files (+-2 degC margin), T_room spans the acceptable band (+-1
    degC margin). Factored out so Task 3 (or anyone rebuilding a stale map)
    uses the exact same grid, rather than re-deriving it and silently drifting."""
    from common import data_io
    _, ambient = data_io.load_raw()
    t_amb_all = np.concatenate(list(ambient.values()))
    t_amb_grid = np.arange(np.floor(t_amb_all.min()) - 1.0,
                            np.ceil(t_amb_all.max()) + 1.01, 1.0)
    t_room_grid = np.arange(config.T_RECOMMENDED_LOW_C - 10.0,
                            config.T_RECOMMENDED_HIGH_C + 10.01, 1.0)
    return t_room_grid, t_amb_grid


def build_map(T_room_grid=None, T_amb_grid=None, bore_mm=None, refrigerant=None):
    """Precompute Q_AC, COP_inner over a (T_room, T_amb) grid, each wrapped in a
    RegularGridInterpolator (Hint 1). With no grid args this uses a wide
    stand-in range; main_task2.py / Task 3 pass the narrower, data-driven grid
    from default_grids() instead.

    Each grid point uses cycle_point's constant-approach cycle -- already the
    optimum, not just a stand-in (see analysis/cop_optimum.py)."""
    if T_room_grid is None:
        T_room_grid = np.arange(13.0, 36.01, 1.0)   # widened: 18-27 band pushes T_room up; don't extrapolate the AC map
    if T_amb_grid is None:
        T_amb_grid = np.arange(0.0, 40.01, 1.0)

    Q = np.zeros((len(T_room_grid), len(T_amb_grid)))
    C = np.zeros_like(Q)
    K = np.zeros_like(Q, dtype=bool)   # clamped (min-ratio) flag
    for i, tr in enumerate(T_room_grid):
        for j, ta in enumerate(T_amb_grid):
            pt = cycle_point(tr, ta, bore_mm, refrigerant)
            Q[i, j] = pt["Q_AC_kW"]
            C[i, j] = pt["COP_inner"]
            K[i, j] = pt["clamped"]

    q_interp = RegularGridInterpolator(
        (T_room_grid, T_amb_grid), Q, bounds_error=False, fill_value=None)
    c_interp = RegularGridInterpolator(
        (T_room_grid, T_amb_grid), C, bounds_error=False, fill_value=None)
    return {
        "T_room_grid": T_room_grid, "T_amb_grid": T_amb_grid,
        "Q_AC": Q, "COP_inner": C, "clamped": K,
        "q_interp": q_interp, "c_interp": c_interp,
    }


def lookup(cmap, T_room_C, T_amb_C):
    """Interpolate (Q_AC_kW, COP_inner) at one (T_room, T_amb)."""
    pt = np.array([[T_room_C, T_amb_C]])
    return float(cmap["q_interp"](pt)[0]), float(cmap["c_interp"](pt)[0])


def map_to_dataframe(cmap):
    """Flatten a build_map() grid into the long-form table (T_amb, T_room,
    Q_AC_kW, COP_inner) that plotting.py's contour plots expect."""
    import pandas as pd
    T_room_grid, T_amb_grid = cmap["T_room_grid"], cmap["T_amb_grid"]
    rows = [
        {"T_room": tr, "T_amb": ta,
         "Q_AC_kW": cmap["Q_AC"][i, j], "COP_inner": cmap["COP_inner"][i, j],
         "clamped": bool(cmap["clamped"][i, j])}
        for i, tr in enumerate(T_room_grid)
        for j, ta in enumerate(T_amb_grid)
    ]
    return pd.DataFrame(rows)


def map_from_dataframe(df):
    """Rebuild a build_map()-shaped cmap (with q_interp/c_interp) from a
    long-form table previously written by map_to_dataframe/save_performance_map.
    Lets Task 3 reuse Task 2's saved (T_room, T_amb) maps directly, instead of
    recomputing the cycle (Hint 1)."""
    T_room_grid = np.sort(df["T_room"].unique())
    T_amb_grid = np.sort(df["T_amb"].unique())
    piv_Q = df.pivot(index="T_room", columns="T_amb", values="Q_AC_kW").loc[T_room_grid, T_amb_grid]
    piv_C = df.pivot(index="T_room", columns="T_amb", values="COP_inner").loc[T_room_grid, T_amb_grid]
    piv_K = df.pivot(index="T_room", columns="T_amb", values="clamped").loc[T_room_grid, T_amb_grid]
    Q, C, K = piv_Q.values, piv_C.values, piv_K.values.astype(bool)

    q_interp = RegularGridInterpolator(
        (T_room_grid, T_amb_grid), Q, bounds_error=False, fill_value=None)
    c_interp = RegularGridInterpolator(
        (T_room_grid, T_amb_grid), C, bounds_error=False, fill_value=None)
    return {
        "T_room_grid": T_room_grid, "T_amb_grid": T_amb_grid,
        "Q_AC": Q, "COP_inner": C, "clamped": K,
        "q_interp": q_interp, "c_interp": c_interp,
    }
