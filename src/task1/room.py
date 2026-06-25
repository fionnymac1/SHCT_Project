"""
Room moist-air model - Exercise 11 extended (Task 1).

State per kg dry air:  z = [h* (kJ/kg_a), m_w (kg)] ;  X = m_w / M_AIR.
    Energy:  M_AIR * dh*/dt = Q_server(t) - Q_cool                    [kW]
    Water:           dm_w/dt = (X_sink - X) * m_dot                   [kg/s]

This is the Exercise-11 room model - same state vector, same energy/water
balances, same condensation two-case - extended for the server room with:
time-varying server load Q_server (replaces the fixed envelope Q), an OFF mode,
and a VENT mode that exchanges enthalpy + water with ambient.

Modes (mutually exclusive, shared fan). Both actuators are strictly ON/OFF and
run at FULL capacity while on; the cooling rate is recomputed at the current
room enthalpy each ODE step so it self-limits physically:
  OFF : no exchange (only the server heat).
  AC  : coil at T_AC, condensation two-case X_sink = min(X, Xsat(T_AC));
        Q_cool = Q_AC (full compressor capacity), recirculation m_dot floats.
  VENT: ambient air (T_amb, phi 0.60) at the fixed design flow rhoV.

Psychrometrics
--------------
All moist-air states come from the course module
Fluid_CP_moist_air.state_moist (CoolProp, p = 1 bar), exactly as Exercise 11:
forward via (T,phi)/(T,X), inversion via (h*,X) (solution cell 16).

ONE deviation from Ex11's call pattern, forced by a verified numerical trap:
state_moist's (T,X) branch is unreliable AT SATURATION - it reconstructs the
water partial pressure on the saturation line and CoolProp resolves the wrong
phase, returning a wrong h* (e.g. 5.90 instead of ~20.8 kJ/kg at 6 degC) or
raising. The AC coil outlet is saturated whenever it dehumidifies, so a
saturated state (X >= X_sat) is evaluated through the robust (T,phi=1) entry
instead, which is exact at every temperature. Ex11 never hit this because its
coil sat at 12 degC, where the (T,X) branch happens to resolve correctly;
this room's coil runs colder (T_AC ~ T_room - 9).

Units: degC, kJ/kg_a, kg, kg/s, s, kW. p = 1 bar.
"""
import numpy as np
from scipy.optimize import fsolve
from common import config
from common import Fluid_CP_moist_air as Fmoist


M_AIR = config.M_AIR_KG          # kg dry air; module global so sensitivity.py
                                 # can override it via `room.M_AIR = ...`.


def state_Tphi(T_C, phi):
    """(X, h*) of a moist-air stream at (T, phi) from ONE state_moist call.
    Used for the ambient air in VENT (phi < 1 there, so the (T,phi) entry is
    robust).  Replaces a separate X-then-h* pair on the same point"""
    z = Fmoist.state_moist(["T", "phi"], [T_C, phi])
    return float(z["X"]), float(z["h*"])


# Define Xsat so it can be called from simulation for varying T_AC
def Xsat(T_C):
    """Saturated water content X_sat at T  (phi = 1)."""
    return float(Fmoist.state_moist(["T", "phi"], [T_C, 1.0])["X"])


# Water-enthalpy reference of the course module (the local h_w0 inside
# state_moist): saturated-liquid water at the triple point (0.01 degC, 611.7 Pa).
_H_W0 = float(Fmoist.state(["T", "p"], [0.01, 611.7e-5], "water", "CBar")["h"])


def hstar(T_C, X):
    """h* [kJ/kg_a] at (T, X), valid on the WHOLE plane incl. the fog region.

    Three regimes about the saturation line X_sat(T):
      X <  X_sat : unsaturated -> module forward (T, X).
      X ~ X_sat  : saturated   -> robust (T, phi=1) entry (the (T,X) branch is
                   numerically unreliable AT saturation; see module docstring).
      X >  X_sat : OVERSATURATED / fog. state_moist returns NaN here. The vapour
                   holds only X_sat; the excess (X - X_sat) has condensed to
                   liquid carrying h_w_liq(T), so
                       h* = h*_sat(T) + (X - X_sat) * h_w_liq(T)
                   (standard Mollier fog enthalpy). Continuous with the saturated
                   value - the added term vanishes at X = X_sat.
    """
    sat = Fmoist.state_moist(["T", "phi"], [T_C, 1.0])     # X_sat and h*_sat
    X_sat, h_sat = float(sat["X"]), float(sat["h*"])
    if X >= X_sat - 1e-9:                                  # saturated or fog
        h_w_liq = float(Fmoist.state(["T", "x"], [T_C, 0.0],
                                     "water", "CBar")["h"]) - _H_W0
        return h_sat + max(0.0, X - X_sat) * h_w_liq       # fog term -> 0 at sat
    return float(Fmoist.state_moist(["T", "X"], [T_C, X])["h*"])


def initial_state():
    """[h*, m_w] at the initial room condition (T_INIT_C, PHI_INIT)."""
    x0 = Fmoist.state_moist(["T", "phi"], [config.T_INIT_C, config.PHI_INIT])
    return [float(x0["h*"]), float(x0["X"]) * M_AIR]


def invert(h_, mw):
    """Recover (T, phi, X) from the state (h*, m_w).

    Exercise 11 (cell 16) uses state_moist(["h*","X"]); that built-in inversion
    queries liquid water at the dew point, so it is only valid for a dew point
    above CoolProp's 0.01 degC triple point.  The AC dries this room to
    ~11-26 % RH (dew point < 0 degC) in every season, where that call CRASHES.
    Instead, T is found by solving the module's OWN forward h*(T,X) = h_ with a
    seeded fsolve (the Ex7 fluid-helper idiom, fsolve(hilf, 303.)), using only the
    robust unsaturated (T,X) evaluation.  This is an exact inverse of the forward
    (no reference bias); phi is then read off the module."""
    X = mw / M_AIR
    T_seed = (h_ - 2501.0 * X) / (1.006 + 1.86 * X)    # closed-form guess
    def res(T):                                         # residual on module forward
        return float(Fmoist.state_moist(["T", "X"], [float(T[0]), X])["h*"]) - h_
    T = float(fsolve(res, T_seed)[0])                  # seeded solve, Ex7 idiom
    phi = float(Fmoist.state_moist(["T", "X"], [T, X])["phi"])
    return T, phi, X


# --------------------------------------------------------- closure B (coil outlet)
# The AC fan runs at a FIXED recirculation flow (config.AC_FAN_FLOW_M3S), so the
# coil-outlet air state is the DEPENDENT variable: outlet enthalpy follows from the
# energy balance  h_sink = h_room - Q_AC/m_dot_air , and (T_AC, X_sink) sit on the
# saturation line when the coil condenses (else dry at X_room), floored at the
# physical air pinch  T_ev + DT_APPROACH_AIR_K  (below it the air would need an
# infinite coil -> the fan is undersized for that Q_AC at this point).
_SAT = None   # cached (T, h_sat, X_sat) along the saturation line, built once


def _sat_tables():
    global _SAT
    if _SAT is None:
        Tg = np.linspace(0.5, 40.0, 80)     # >0.01 C water triple point (CoolProp)
        Hg, Xg = [], []
        for Tc in Tg:
            z = Fmoist.state_moist(["T", "phi"], [float(Tc), 1.0])
            Hg.append(float(z["h*"])); Xg.append(float(z["X"]))
        _SAT = (Tg, np.array(Hg), np.array(Xg))
    return _SAT


def _T_dry(h_target, X):
    """T with hstar(T, X) = h_target  (unsaturated; seeded fsolve on the module
    forward, same scheme as invert())."""
    T_seed = (h_target - 2501.0 * X) / (1.006 + 1.86 * X)   # closed-form guess
    def res(T):                                             # residual on hstar
        return hstar(float(T[0]), X) - h_target
    return float(fsolve(res, T_seed)[0])                    # seeded solve, Ex7 idiom


def coil_outlet_B(h_room, X_room, Q_AC, m_dot_AC, T_ev_C):
    """Closure-B AC coil outlet at the FIXED recirc mass flow m_dot_AC [kg/s].
    Outlet enthalpy h_sink = h_room - Q_AC/m_dot_AC; (T_AC, X_sink) on the
    saturation line if condensing, else dry; floored at T_ev + air pinch.
    Returns (h_sink, T_AC, X_sink, fan_ok)."""
    Tg, Hg, Xg = _sat_tables()
    h_sink = h_room - Q_AC / m_dot_AC
    T_wet = float(np.interp(h_sink, Hg, Tg))               # saturation-line inverse
    X_sat_wet = float(np.interp(T_wet, Tg, Xg))
    if X_room >= X_sat_wet:                                # coil condenses (wet)
        T_AC, X_sink = T_wet, X_sat_wet
    else:                                                  # dry cooling, X unchanged
        T_AC, X_sink = _T_dry(h_sink, X_room), X_room
    T_floor = T_ev_C + config.DT_APPROACH_AIR_K
    fan_ok = T_AC >= T_floor - 1e-9
    if not fan_ok:                                         # undersized: clamp to pinch
        T_AC = T_floor
        X_sink = min(X_room, float(np.interp(T_AC, Tg, Xg)))
        h_sink = hstar(T_AC, X_sink)                       # Q absorbed < Q_AC
    return h_sink, T_AC, X_sink, fan_ok


def rhs(z, t, mode, p):
    """ODE RHS for true on/off. The instantaneous cooling rate is evaluated at
    the current room enthalpy h_ (not frozen at the step start), so it
    self-limits as the room approaches the heat sink."""
    h_, mw = z
    X = mw / M_AIR
    Q_server = p["Q_server"]
    if mode == "AC":
        # Closure B: recirc flow is FIXED (the fan); p["h_sink"] = h_room_start
        # - Q_AC/m_dot was derived from it. Q_cool = m_dot*(h_-h_sink) self-limits
        # as the room cools (equals Q_AC at the step start).
        denom = h_ - p["h_sink"]
        m_dot = p["m_dot_AC"] if denom > 0.0 else 0.0
        Q_cool = m_dot * denom
        dhdt = (Q_server - Q_cool) / M_AIR
        dmwdt = (p["X_sink"] - X) * m_dot
    elif mode == "VENT":
        denom = h_ - p["h_amb"]
        if denom > 1e-6:
            m_dot = p["rhoV"]                  # fixed design air flow
            Q_cool = m_dot * denom             # -> 0 as room -> ambient
        else:
            Q_cool = m_dot = 0.0
        dhdt = (Q_server - Q_cool) / M_AIR
        dmwdt = (p["X_amb"] - X) * m_dot
    else:
        dhdt = Q_server / M_AIR
        dmwdt = 0.0
    return [dhdt, dmwdt]
