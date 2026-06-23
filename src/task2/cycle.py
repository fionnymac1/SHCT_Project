"""
Subcritical vapour-compression cycle - Task-1 stand-in (one bore + refrigerant).
Generalised over (bore, refrigerant) in Task 3.

Per Hint 1 (slide 10): the cycle is NOT re-solved every timestep. We precompute
COP_inner and cooling capacity Q_AC on a (T_room, T_amb) grid and interpolate
during the time simulation.

Cycle definition (constant approaches, also off-design):
    T_ev = T_room - DT_APPROACH_EVAP_K
    T_co = T_amb  + DT_APPROACH_COND_K
    1: compressor suction  = sat. vapour at T_ev + superheat
    2: discharge           = isentropic to p_co, corrected by eta_is
    3: condenser outlet    = sat. liquid at T_co (minus subcooling)
    4: evaporator inlet    = isenthalpic expansion (h4 = h3)
    q_evap = h1 - h4   (refrigerating effect, kJ/kg)
    w_comp = h2 - h1   (specific work,        kJ/kg)
    COP_inner = q_evap / w_comp,   Q_AC = m_dot * q_evap

Minimum-pressure-ratio envelope (p_co/p_ev >= MIN_PRESSURE_RATIO): at low lift
the natural ratio falls below the limit. We then CLAMP the condenser pressure
up to MIN_PRESSURE_RATIO * p_ev (compressor holds a minimum head); the cycle
stays operable at a COP penalty. Without this there is an uncooled gap in mild
weather (ambient too warm for free cooling, lift too small for the envelope).

States via the course wrapper Fluid_CP.state (Eh='CBar' -> degC, bar, kJ/kg).
Compressor mass flow + isentropic efficiency from the provided module.
"""
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from common import config, Fluid_CP as FCP, compressor_model as comp
from scipy.optimize import minimize

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
        "Q_AC_kW": Q_AC, "W_kW": W, "COP_inner": cop,
        "T_AC": T_ev + config.DT_APPROACH_AIR_K,
        "dt_sc_actual": dt_sc
    }

def optimize_cop(T_room_C, T_amb_C, bore_mm=None, refrigerant=None):
    """
    Floats both Condensation Temperature and Subcooling to maximize COP_inner.
    Locks Evaporation Temperature and Superheat as technical constraints.
    """
    bore_mm = config.STANDIN_BORE_MM if bore_mm is None else bore_mm
    refrigerant = config.STANDIN_REFRIGERANT if refrigerant is None else refrigerant
    
    # 1. Lock the required technical constraints
    fixed_T_ev = T_room_C - config.DT_APPROACH_EVAP_K
    fixed_dt_sh = config.DELTA_T_SUPERHEAT_K

    # 2. Objective Function to MINIMIZE (Negative COP)
    def objective(x):
        float_T_co = x[0]
        float_dt_sc = x[1]
        
        try:
            # Call the updated cycle_point with the floating variables
            res = cycle_point(
                T_room_C=T_room_C, 
                T_amb_C=T_amb_C, 
                bore_mm=bore_mm, 
                refrigerant=refrigerant,
                dt_sh=fixed_dt_sh,    # Locked
                dt_sc=float_dt_sc,    # FLOATING
                T_ev_C=fixed_T_ev,    # Locked
                T_co_C=float_T_co     # FLOATING
            )
            
            if res["COP_inner"] <= 0:
                return 1e6
            return -res["COP_inner"] 
        except Exception:
            # Catch fluid boundary errors from the CoolProp wrapper
            return 1e6 
            
    # 3. Initial Guesses (Start at the config defaults)
    x0 = [T_amb_C + config.DT_APPROACH_COND_K, config.DELTA_T_SUBCOOL_K]
    
    # 4. Bounds
    # T_co must be warmer than ambient to reject heat. Capped arbitrarily at 80C.
    # dt_sc can range from 0K to a realistic physical limit (e.g., 20K).
    bounds = [
        (T_amb_C + 0.1, 80.0), 
        (0.0, 20.0)            
    ]
    
    # 5. Constraints
    # The subcooled liquid temperature (T_co - dt_sc) CANNOT be colder than 
    # the ambient air (T_amb) cooling it.
    # Mathematically: (T_co - dt_sc) >= T_amb  -->  (T_co - dt_sc) - T_amb >= 0
    def subcool_limit_constraint(x):
        float_T_co = x[0]
        float_dt_sc = x[1]
        return (float_T_co - float_dt_sc) - T_amb_C
        
    cons = ({'type': 'ineq', 'fun': subcool_limit_constraint})

    # 6. Run the Solver
    sol = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons)
    
    # 7. Return Results
    if sol.success:
        optimal_T_co = sol.x[0]
        optimal_dt_sc = sol.x[1]
        
        # Recalculate and return the full dictionary at the mathematically proven peak
        return cycle_point(
            T_room_C, T_amb_C, bore_mm, refrigerant, 
            dt_sh=fixed_dt_sh, dt_sc=optimal_dt_sc, 
            T_ev_C=fixed_T_ev, T_co_C=optimal_T_co
        )
    else:
        # Fallback to the standard unoptimized config if the solver fails to converge
        return cycle_point(T_room_C, T_amb_C, bore_mm, refrigerant)

def build_map(T_room_grid=None, T_amb_grid=None, bore_mm=None, refrigerant=None):
    """Precompute Q_AC, COP_inner over a (T_room, T_amb) grid, each wrapped in a
    RegularGridInterpolator (Hint 1)."""
    if T_room_grid is None:
        T_room_grid = np.arange(13.0, 36.01, 1.0)   # widened: 18-27 band pushes T_room up; don't extrapolate the AC map
    if T_amb_grid is None:
        T_amb_grid = np.arange(0.0, 40.01, 2.0)

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
