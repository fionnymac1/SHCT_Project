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
from common import config
from common import Fluid_CP_moist_air as Fmoist


M_AIR = config.M_AIR_KG          # kg dry air; module global so sensitivity.py
                                 # can override it via `room.M_AIR = ...`.


def state_Tphi(T_C, phi):
    """(X, h*) of a moist-air stream at (T, phi) from ONE state_moist call.
    Used for the ambient air in VENT (phi < 1 there, so the (T,phi) entry is
    robust).  Replaces a separate X-then-h* pair on the same point, halving the
    state_moist calls per VENT step."""
    s = Fmoist.state_moist(["T", "phi"], [T_C, phi])
    return float(s["X"]), float(s["h*"])


def Xsat(T_C):
    """Saturated water content X_sat at T  (phi = 1)."""
    return float(Fmoist.state_moist(["T", "phi"], [T_C, 1.0])["X"])


def hstar(T_C, X):
    """h* [kJ/kg_a] at (T, X) via state_moist.  A saturated X (X >= X_sat, e.g.
    the dehumidifying coil outlet) is routed through the robust (T,phi=1) entry;
    state_moist's (T,X) branch returns a wrong h* or raises at saturation
    (verified for T in ~4-10 degC).  See module docstring."""
    sat = Fmoist.state_moist(["T", "phi"], [T_C, 1.0])     # X_sat and h*_sat
    if X >= float(sat["X"]) - 1e-9:
        return float(sat["h*"])                            # saturated / clamped
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
    Instead, T is found by solving the module's OWN forward h*(T,X) = h_ (Newton,
    seeded with the closed-form guess), using only the robust unsaturated (T,X)
    evaluation.  This is an exact inverse of the forward (no reference bias);
    phi is then read off the module."""
    X = mw / M_AIR
    T = (h_ - 2501.0 * X) / (1.006 + 1.86 * X)         # closed-form seed only
    for _ in range(6):                                  # Newton on module forward
        dT = (h_ - float(Fmoist.state_moist(["T", "X"], [T, X])["h*"])) \
             / (1.006 + 1.86 * X)
        T += dT
        if abs(dT) < 1e-4:
            break
    phi = float(Fmoist.state_moist(["T", "X"], [T, X])["phi"])
    return T, phi, X


def enthalpy_at(T_C, X):
    return hstar(T_C, X)


def rhs(z, t, mode, p):
    """ODE RHS for true on/off. The instantaneous cooling rate is evaluated at
    the current room enthalpy h_ (not frozen at the step start), so it
    self-limits as the room approaches the heat sink."""
    h_, mw = z
    X = mw / M_AIR
    Q_server = p["Q_server"]
    if mode == "AC":
        denom = h_ - p["h_sink"]
        if denom > 1e-6:
            Q_cool = p["Q_AC"]                 # full compressor capacity
            m_dot = Q_cool / denom             # recirculation flow floats
        else:                                  # room at/below the coil enthalpy
            Q_cool = m_dot = 0.0
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
