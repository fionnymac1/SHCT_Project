"""
Task 1 time-simulation driver: integrate the room ODE under the on/off control
state machine over each representative season-day at the 5-min control step.

Modelling choice (justified): the cooling is delivered at VARIABLE capacity,
modulated to hold a mid-band setpoint and capped at the available capacity.
Fixed-speed on/off cannot hold a 15-18 C band on this small thermal mass
(216 kg, ~217 kJ/K) at a 5-min step with a 10-min minimum standstill - one
forced step overshoots the band by many K. Variable-speed is also standard for
server-room precision cooling. Modulation IS the part-load ratio, so Hint 2's
COP_res penalty (which punishes oversized capacity) falls out directly.

AC capacity Q_AC and COP_inner come from the precomputed (T_room,T_amb) map
(Hint 1, interpolated). Run from the repository root.
"""
import numpy as np
from scipy.integrate import odeint
import pandas as pd
import config, data_io, room, control, cycle, flow_limits
import Fluid_CP_moist_air as FCP
from compressor_model import recip_comp_corr_SP


# [ASSUMPTION][FLAG] fan electrical model (not given): specific fan power.
FAN_SPECIFIC_POWER_KW_PER_M3S = 1.0
VENT_FLOW_MAX_M3S = flow_limits.v_max_acoustic_m3s()
T_SET_C = 0.5 * (config.T_OFF_C + config.T_ON_C)          # mid-band target


def cop_res(cop_inner, Q_cool, Q_AC):
    """Hint 2 resulting COP at part-load PLR = Q_cool / Q_AC_max."""
    if Q_AC <= 0:
        return cop_inner
    plr = min(Q_cool / Q_AC, 1.0)
    if plr <= 0:
        return cop_inner
    return cop_inner * plr / (config.PART_LOAD_A * plr + config.PART_LOAD_B)


def simulate_season(season, cmap):
    server_raw, amb_raw = data_io.load_raw()
    t, q_srv = data_io.resample_day(server_raw)
    _, q_amb = data_io.resample_day(amb_raw[season])
    N = len(t)
    dt_s = config.TIME_STEP_MIN * 60.0

    T = np.zeros(N); PHI = np.zeros(N); X = np.zeros(N)
    MODE = np.empty(N, dtype=object)
    QCOOL = np.zeros(N); QAC = np.zeros(N); QDEM = np.zeros(N)
    WEL = np.zeros(N); COPR = np.zeros(N)

    z = room.initial_state()
    T[0], PHI[0], X[0] = room.invert(*z)
    state, steps = "OFF", control.MIN_STANDSTILL_STEPS
    MODE[0] = state; QDEM[0] = q_srv[0]

    for i in range(1, N):
        T_room, T_amb, Q_srv = T[i - 1], q_amb[i], q_srv[i]
        new = control.decide(state, steps, T_room, T_amb, Q_srv)
        steps = steps + 1 if new == state else 1
        state = new

        h_room, X_now = z[0], z[1] / room.M_AIR
        # cooling required this step to reach the mid-band setpoint
        h_set = room.enthalpy_at(T_SET_C, X_now)
        Q_req = Q_srv + room.M_AIR * (h_room - h_set) / dt_s

        if state == "AC":
            Q_AC, cop_in = cycle.lookup(cmap, T_room, T_amb)
            Q_cool = float(np.clip(Q_req, 0.0, Q_AC))
            T_AC = T_room - config.DT_APPROACH_EVAP_K + config.DT_APPROACH_AIR_K
            X_sat = room.Xsat(T_AC)
            X_sink = min(X_now, X_sat)                       # condensation 2-case
            h_sink = room.hstar(T_AC, X_sink)
            p = {"Q_server": Q_srv, "Q_cool": Q_cool,
                 "h_sink": h_sink, "X_sink": X_sink}
            cr = cop_res(cop_in, Q_cool, Q_AC)
            WEL[i] = Q_cool / cr if cr > 0 else 0.0
            QAC[i], COPR[i] = Q_AC, cr
        elif state == "VENT":
            X_amb = room.X_from_Tphi(T_amb, config.VENT_AMBIENT_PHI)
            h_amb = room.hstar(T_amb, X_amb)
            Q_cap = max(room.M_AIR * 0.0,
                        config.AIR_DENSITY_KG_M3 * VENT_FLOW_MAX_M3S * (h_room - h_amb))
            Q_cool = float(np.clip(Q_req, 0.0, Q_cap))
            p = {"Q_server": Q_srv, "Q_cool": Q_cool, "h_sink": h_amb, "X_sink": X_amb}
            v_dot = (Q_cool / (h_room - h_amb) / config.AIR_DENSITY_KG_M3
                     if h_room > h_amb else 0.0)
            WEL[i] = FAN_SPECIFIC_POWER_KW_PER_M3S * v_dot
        else:
            Q_cool = 0.0
            p = {"Q_server": Q_srv}

        zz = odeint(room.rhs, z, [0.0, dt_s], args=(state, p))
        z = list(zz[-1])
        T[i], PHI[i], X[i] = room.invert(*z)
        MODE[i] = state; QCOOL[i] = Q_cool; QDEM[i] = Q_srv

    return _summarise(season, t, T, PHI, X, MODE, QCOOL, QAC, QDEM, WEL, COPR)


def _count_starts(mode, label):
    return int(sum(1 for i in range(1, len(mode))
                   if mode[i] == label and mode[i - 1] != label))


def _summarise(season, t, T, PHI, X, MODE, QCOOL, QAC, QDEM, WEL, COPR):
    dt_h = config.TIME_STEP_MIN / 60.0
    in_band = np.mean((T >= config.T_BAND_LOW_C) & (T <= config.T_BAND_HIGH_C))
    return {
        "season": season, "t": t, "T": T, "phi": PHI, "X": X, "mode": MODE,
        "Q_cool": QCOOL, "Q_AC": QAC, "Q_dem": QDEM, "W_el": WEL, "COP_res": COPR,
        "T_min": float(T.min()), "T_max": float(T.max()),
        "phi_min": float(PHI.min()), "phi_max": float(PHI.max()),
        "frac_in_band": float(in_band),
        "ac_starts": _count_starts(MODE, "AC"),
        "vent_starts": _count_starts(MODE, "VENT"),
        "ac_min": float(np.sum(MODE == "AC") * config.TIME_STEP_MIN),
        "vent_min": float(np.sum(MODE == "VENT") * config.TIME_STEP_MIN),
        "off_min": float(np.sum(MODE == "OFF") * config.TIME_STEP_MIN),
        "E_ac_kWh": float(np.sum(WEL * (MODE == "AC")) * dt_h),
        "E_vent_kWh": float(np.sum(WEL * (MODE == "VENT")) * dt_h),
    }

def calculate_ac_performance(T_amb, T_room, refrigerant, D_bore):
    """
    Calculates the AC cooling capacity and COP_inner for a specific ambient temperature.
    
    Parameters:
    - T_amb (float): Ambient outside temperature in °C.
    - T_room (float): Room temperature in °C.
    - refrigerant (str): Refrigerant name (e.g., "Propane", "R1234yf", "Dimethyl ether").
    - D_bore (float): Compressor cylinder diameter in mm (30, 40, or 50).
    
    Returns:
    - tuple: (Q_AC_kW, COP_inner, P_elec_kW)
    """
    # Design Assumptions (Standard Engineering Baseline)
    dT_approach = 5.0    # K (Approach temperature for heat exchangers)
    dT_sh = 5.0          # K (Superheat)
    dT_sc = 0.0          # K (Subcooling - assumed zero unless specified)
    
    # 1. Establish Ideal Boundary Temperatures
    T_ev = T_room - dT_approach
    T_co_ideal = T_amb + dT_approach
    
    # 2. Get Pressures to check the operating envelope
    state_ev = FCP.state(["T", "x"], [T_ev, 1.0], refrigerant, Eh="CBar")
    P_ev = state_ev["p"]
    
    state_co_ideal = FCP.state(["T", "x"], [T_co_ideal, 0.0], refrigerant, Eh="CBar")
    P_co_ideal = state_co_ideal["p"]
    
    # 3. Enforce Minimum Pressure Ratio of 2.0
    if (P_co_ideal / P_ev) < 2.0:
        P_co_real = P_ev * 2.0
        # Recalculate condensing temperature at this forced higher pressure
        state_co_real = FCP.state(["p", "x"], [P_co_real, 0.0], refrigerant, Eh="CBar")
        T_co = state_co_real["T"]
    else:
        P_co_real = P_co_ideal
        T_co = T_co_ideal
        
    # 4. Call the empirical compressor model
    # param format required: (T_ev, T_co, DeltaT_sh, DeltaT_sc, D)
    param = (T_ev, T_co, dT_sh, dT_sc, D_bore)
    eta_is, m_dot = recip_comp_corr_SP(param, refrigerant, transcrit=False)
    
    # 5. Extract specific enthalpies for power calculations
    # State 1: Compressor Inlet (Evaporating pressure + Superheat)
    T1 = T_ev + dT_sh
    state1 = FCP.state(["T", "p"], [T1, P_ev], refrigerant, Eh="CBar")
    h1 = state1["h"]  # kJ/kg
    s1 = state1["s"]
    
    # State 2s: Isentropic Compressor Outlet
    state2s = FCP.state(["p", "s"], [P_co_real, s1], refrigerant, Eh="CBar")
    h2s = state2s["h"] # kJ/kg
    
    # State 3: Condenser Outlet (Liquid)
    # Assumes expansion is isenthalpic, so h3 = h4 (Evaporator inlet)
    # With dT_sc=0, T3 == T_co lands exactly on the saturation dome, where (T,p)
    # no longer uniquely defines a state -> query via quality (x=0) instead.
    if dT_sc <= 0:
        state3 = FCP.state(["p", "x"], [P_co_real, 0.0], refrigerant, Eh="CBar")
    else:
        T3 = T_co - dT_sc
        state3 = FCP.state(["T", "p"], [T3, P_co_real], refrigerant, Eh="CBar")
    h3 = state3["h"] # kJ/kg
    
    # 6. Calculate System Performance
    # Specific work and heat (kJ/kg)
    w_is = h2s - h1
    w_real = w_is / eta_is
    q_evap = h1 - h3
    
    # Total Power (Mass Flow [kg/s] * Specific Energy [kJ/kg] = kW)
    Q_AC_kW = m_dot * q_evap
    P_elec_kW = m_dot * w_real
    COP_inner = Q_AC_kW / P_elec_kW
    
    return Q_AC_kW, COP_inner, P_elec_kW


def generate_performance_map(refrigerant, D_bore):
    ambient_temps = np.arange(-15, 41, 1)
    room_temps    = np.arange(10, 22, 1)        # source axis, matching the slide
    results = []
    for T_amb in ambient_temps:
        for T_room in room_temps:
            Q, cop, P = calculate_ac_performance(T_amb, T_room, refrigerant, D_bore)
            results.append({"T_amb": T_amb, "T_room": T_room,
                            "Q_AC_kW": Q, "COP_inner": cop, "P_elec_kW": P})
    df_map = pd.DataFrame(results)
    df_map.to_csv(f"ac_map_{refrigerant}_{D_bore:.0f}mm.csv", index=False)
    return df_map

def simulate_all(cmap=None):
    if cmap is None:
        cmap = cycle.build_map()
    return {s: simulate_season(s, cmap) for s in config.SEASONS}
