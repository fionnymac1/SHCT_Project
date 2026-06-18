"""
Room moist-air model - Exercise 11 extended (Task 1).

State per kg dry air:  z = [h* (kJ/kg_a), m_w (kg)] ; X = m_w / M_AIR.
    Energy:  M_AIR * dh*/dt = Q_server(t) - Q_cool                    [kW]
    Water:           dm_w/dt = (X_sink - X) * m_dot                   [kg/s]

Modes (mutually exclusive, shared fan):
  OFF : no exchange (only the server heat).
  AC  : coil at T_AC, condensation two-case X_sink = min(X, Xsat(T_AC));
        m_dot = Q_cool / (h*_room - h*_sink).
  VENT: ambient air (T_amb, phi 0.60), X_sink = X_amb; same m_dot form.

Psychrometrics
--------------
The course module Fluid_CP_moist_air.state_moist is exact but slow (CoolProp +
a brentq inversion per call) and throws once the room dries below water's
triple point. The room balance is integrated many times, so here we use the
standard ideal-gas moist-air relations
    h* = cp_a T + X (hfg0 + cp_v T)          [kJ/kg dry air]
with a Magnus psat. These are the SAME physics state_moist encodes; agreement
is validated in tests/validate_psychro (max |dT| ~ 0.1-0.3 K, |dphi| ~ 1 %).
Units: degC, kJ/kg_a, kg, kg/s, s, kW. p = 1 bar.
"""
import numpy as np

from src import config

M_AIR = config.M_AIR_KG
P_KPA = config.P_BAR * 100.0
CP_A, CP_V, HFG0 = 1.006, 1.86, 2501.0          # kJ/kg(.K), 0 degC reference


def psat_kPa(T_C):
    """Saturation pressure of water (Magnus), kPa."""
    return 0.61094 * np.exp(17.625 * T_C / (T_C + 243.04))


def X_from_Tphi(T_C, phi):
    pw = phi * psat_kPa(T_C)
    return 0.622 * pw / (P_KPA - pw)


def Xsat(T_C):
    return X_from_Tphi(T_C, 1.0)


def hstar(T_C, X):
    return CP_A * T_C + X * (HFG0 + CP_V * T_C)


def T_from_hX(h_, X):
    return (h_ - HFG0 * X) / (CP_A + CP_V * X)


def phi_from_TX(T_C, X):
    pw = X * P_KPA / (0.622 + X)
    return pw / psat_kPa(T_C)


def initial_state():
    X0 = X_from_Tphi(config.T_INIT_C, config.PHI_INIT)
    return [hstar(config.T_INIT_C, X0), X0 * M_AIR]


def invert(h_, mw):
    X = mw / M_AIR
    T = T_from_hX(h_, X)
    return T, phi_from_TX(T, X), X


def enthalpy_at(T_C, X):
    return hstar(T_C, X)


def rhs(z, t, mode, p):
    """Pure-arithmetic ODE RHS; h_sink, X_sink precomputed once per step."""
    h_, mw = z
    X = mw / M_AIR
    Q_server = p["Q_server"]
    if mode in ("AC", "VENT"):
        Q_cool = p["Q_cool"]
        dh = (Q_server - Q_cool) / M_AIR
        denom = h_ - p["h_sink"]
        m_dot = Q_cool / denom if denom > 1e-6 else 0.0
        dmw = (p["X_sink"] - X) * m_dot
    else:
        dh = Q_server / M_AIR
        dmw = 0.0
    return [dh, dmw]
