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
import numpy as np
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
    z3 = FCP.state(["T", "p"], [T_co - dt_sc, p_co], refrigerant, Eh=EH)    # subcooled liquid
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


if __name__ == "__main__":
    # Verification: the SLSQP optimum must reproduce the constant-approach cycle.
    from task2 import cycle
    hdr = "  point         opt-COP  appr_ev appr_co p_ratio  ok |  map-COP  clamp"
    print(hdr)
    for T_room, T_amb in [(15, 30), (22, 35), (15, 2)]:
        o = optimize_cop(T_room, T_amb)
        c = cycle.cycle_point(T_room, T_amb)
        match = abs(o["COP"] - c["COP_inner"]) < 0.02
        print("  T_room=%2d T_amb=%2d   %.3f   %5.1f   %5.1f   %.2f  %s |  %.3f   %s"
              % (T_room, T_amb, o["COP"], o["approach_evap"], o["approach_cond"],
                 o["p_ratio"], "Y" if match else "N", c["COP_inner"], c["clamped"]))
