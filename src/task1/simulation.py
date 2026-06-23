"""
Task 1 time-simulation driver: integrate the room ODE under the on/off control
state machine over each representative season-day at the 5-min control step.

Modelling choice (per task sheet): the AC compressor and the ventilator are
strictly ON/OFF. While ON each runs at FULL capacity - the compressor flat out
(full Q_AC at the current operating point), the fan at its single design flow.
There is NO capacity modulation; the only control is the hysteresis state
machine in control.py switching between {OFF, VENT, AC}. Hint-2 part-load
losses therefore enter through the DUTY CYCLE rather than a throttled capacity:
COP_res is keyed to the demand/capacity ratio Q_server/Q_AC (see cop_res).

AC capacity Q_AC and COP_inner come from the precomputed (T_room,T_amb) map
(Hint 1, interpolated). Run from the repository root.
"""
import numpy as np
from scipy.integrate import odeint
from common import config, data_io
from task1 import room, control, flow_limits
from task2 import cycle


# [ASSUMPTION][FLAG] fan electrical model (not given): specific fan power.
FAN_SPECIFIC_POWER_KW_PER_M3S = 1.0
# ON/OFF ventilator runs at the single DESIGN flow (config), NOT the acoustic
# cap. Full sizing + ASHRAE TC9.9 rationale: see config.VENT_FLOW_DESIGN_M3S.
# Guard that the chosen design flow respects the Beaufort-5 acoustic cap.
VENT_FLOW_DESIGN_M3S = config.VENT_FLOW_DESIGN_M3S
assert VENT_FLOW_DESIGN_M3S <= flow_limits.v_max_acoustic_m3s() + 1e-9, \
    "ventilation design flow exceeds the Beaufort-5 acoustic cap"


def cop_res(cop_inner, Q_demand, Q_AC):
    """Hint 2 part-load COP. Under on/off the compressor delivers the full Q_AC
    whenever it runs, so the part-load ratio is NOT a throttled capacity but the
    time-averaged duty needed to hold the room: PLR = Q_demand / Q_AC, with
    Q_demand = the load to reject (~ Q_server). Oversized capacity -> small PLR
    -> the (0.9*PLR + 0.1) denominator bites; this is the Task-3 bore lever.
    (Keying PLR to Q_cool/Q_AC would give 1.0 here - on/off delivers full Q_AC -
    and silently delete the penalty.)"""
    if Q_AC <= 0:
        return cop_inner
    plr = min(Q_demand / Q_AC, 1.0)
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
    state = "OFF"
    comp_run, comp_idle = 0, control.MIN_STANDSTILL_STEPS   # compressor timers
    MODE[0] = state; QDEM[0] = q_srv[0]

    for i in range(1, N):
        T_room, T_amb, Q_srv = T[i - 1], q_amb[i], q_srv[i]
        new = control.decide(state, comp_run, comp_idle, T_room, T_amb, Q_srv)
        if new == "AC":
            comp_run += 1; comp_idle = 0
        else:
            comp_idle += 1; comp_run = 0
        state = new

        h_room, X_now = z[0], z[1] / room.M_AIR

        if state == "AC":
            # ON/OFF: compressor flat out -> full capacity at this operating pt.
            Q_AC, cop_in = cycle.lookup(cmap, T_room, T_amb)
            T_AC = T_room - config.DT_APPROACH_EVAP_K + config.DT_APPROACH_AIR_K
            X_sink = min(X_now, room.Xsat(T_AC))            # condensation 2-case
            h_sink = room.hstar(T_AC, X_sink)
            p = {"Q_server": Q_srv, "Q_AC": Q_AC,
                 "h_sink": h_sink, "X_sink": X_sink}
            # Hint 2 part-load keyed to demand/capacity (see cop_res docstring).
            cr = cop_res(cop_in, Q_srv, Q_AC)
            WEL[i] = Q_AC / cr if cr > 0 else 0.0           # full-capacity draw
            QCOOL[i] = Q_AC
            QAC[i], COPR[i] = Q_AC, cr
        elif state == "VENT":
            # ON/OFF: fan at its single design speed -> full acoustic flow.
            X_amb, h_amb = room.state_Tphi(T_amb, config.VENT_AMBIENT_PHI)
            rhoV = config.AIR_DENSITY_KG_M3 * VENT_FLOW_DESIGN_M3S
            p = {"Q_server": Q_srv, "rhoV": rhoV, "h_amb": h_amb, "X_amb": X_amb}
            WEL[i] = FAN_SPECIFIC_POWER_KW_PER_M3S * VENT_FLOW_DESIGN_M3S
            QCOOL[i] = max(0.0, rhoV * (h_room - h_amb))    # start-of-step trace
        else:
            p = {"Q_server": Q_srv}
            QCOOL[i] = 0.0

        zz = odeint(room.rhs, z, [0.0, dt_s], args=(state, p))
        z = list(zz[-1])
        T[i], PHI[i], X[i] = room.invert(*z)
        MODE[i] = state; QDEM[i] = Q_srv

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

def simulate_all(cmap=None):
    if cmap is None:
        cmap = cycle.build_map()
    return {s: simulate_season(s, cmap) for s in config.SEASONS}
