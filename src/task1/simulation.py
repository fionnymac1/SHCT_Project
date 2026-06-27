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
import warnings
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

    # Per-combo AC recirc flow, DERIVED from THIS map's capacity (not a config
    # constant): size to the max Q_AC over the room's AC-on operating window so the
    # coil outlet keeps its >=AIR pinch above T_ev at every on-step. Capacity ~bore^2,
    # so each (bore, refrigerant) gets its own fan. Cached on the map; the single-
    # ventilator coupling (acoustic cap + vent->AC turndown) is asserted once.
    if "V_AC_fan_m3s" not in cmap:
        V_sized, cmap["Q_AC_max_oper_kW"] = flow_limits.ac_fan_flow_from_map(cmap)
        cmap["V_AC_fan_m3s"], cmap["vent_ac_turndown"], _ = \
            flow_limits.check_ac_fan_feasible(V_sized)
    V_AC_fan = cmap["V_AC_fan_m3s"]

    # No-damper coupling (control.VENT_USES_AC_FLOW): VENT runs at the per-combo AC
    # recirc flow instead of the gentle design flow. getattr fallback -> the original
    # control.py (no such symbol) keeps the two-flow baseline, nothing else to revert.
    V_vent = (control.vent_flow_m3s(V_AC_fan, VENT_FLOW_DESIGN_M3S)
              if hasattr(control, "vent_flow_m3s") else VENT_FLOW_DESIGN_M3S)

    # Free-cooling flow should not overshoot the low band on its worst forced step
    # (coldest ambient, lowest server, min run); WARN (not crash) so the sweep keeps
    # every candidate and the design choice stays visible. Binds at winter.
    _t_land, _vent_ok = flow_limits.vent_overshoot_ok(
        V_vent, float(np.min(q_amb)), float(np.min(q_srv)))
    if not _vent_ok:
        warnings.warn("%s: a worst forced VENT step lands at %.1f degC, below the "
                      "%.1f degC low band -> consider a lower design flow."
                      % (season, _t_land, config.T_RECOMMENDED_LOW_C))

    T = np.zeros(N); PHI = np.zeros(N); X = np.zeros(N)
    MODE = np.empty(N, dtype=object)
    QCOOL = np.zeros(N); QAC = np.zeros(N); QDEM = np.zeros(N)
    WCOMP = np.zeros(N); WFAN = np.zeros(N); COPR = np.zeros(N)

    z = room.initial_state()
    T[0], PHI[0], X[0] = room.invert(*z)
    state = "OFF"
    comp_run, comp_idle = 0, control.MIN_STANDSTILL_STEPS   # compressor timers
    fan_under = 0                                           # closure-B undersize flag
    MODE[0] = state; QDEM[0] = q_srv[0]

    for i in range(1, N):
        T_room, T_amb, Q_srv = T[i - 1], q_amb[i], q_srv[i]
        new = control.decide(state, comp_run, comp_idle, T_room, T_amb)
        if new == "AC":
            comp_run += 1; comp_idle = 0
        else:
            comp_idle += 1; comp_run = 0
        state = new

        h_room, X_now = z[0], z[1] / room.M_AIR

        if state == "AC":
            # ON/OFF: compressor flat out -> full capacity at this operating pt.
            Q_AC, cop_in = cycle.lookup(cmap, T_room, T_amb)
            # Closure B: fixed recirc flow (the AC fan) -> the coil outlet
            # (h_sink, T_AC, X_sink) is DERIVED from the air energy balance + the
            # saturation line, floored at T_ev + air pinch (fan_ok flags undersize).
            T_ev = T_room - config.DT_APPROACH_EVAP_K
            m_dot_AC = config.AIR_DENSITY_KG_M3 * V_AC_fan
            h_sink, T_AC, X_sink, fan_ok = room.coil_outlet_B(
                h_room, X_now, Q_AC, m_dot_AC, T_ev)
            if not fan_ok:
                fan_under += 1
            p = {"Q_server": Q_srv, "Q_AC": Q_AC, "m_dot_AC": m_dot_AC,
                 "h_sink": h_sink, "X_sink": X_sink}
            # Hint 2 part-load keyed to demand/capacity (see cop_res docstring).
            cr = cop_res(cop_in, Q_srv, Q_AC)
            WCOMP[i] = Q_AC / cr if cr > 0 else 0.0         # compressor full-capacity draw
            # Shared ventilator also runs during AC (it drives the coil recirc
            # flow V_AC_fan) -- same fan the task sheet says VENT and the AC
            # evaporator airflow have in common, so it draws fan power here too.
            WFAN[i] = FAN_SPECIFIC_POWER_KW_PER_M3S * V_AC_fan
            QCOOL[i] = Q_AC
            QAC[i], COPR[i] = Q_AC, cr
        elif state == "VENT":
            # ON/OFF: fan at its single design speed -> full acoustic flow.
            X_amb, h_amb = room.state_Tphi(T_amb, config.VENT_AMBIENT_PHI)
            rhoV = config.AIR_DENSITY_KG_M3 * V_vent
            p = {"Q_server": Q_srv, "rhoV": rhoV, "h_amb": h_amb, "X_amb": X_amb}
            WFAN[i] = FAN_SPECIFIC_POWER_KW_PER_M3S * V_vent
            QCOOL[i] = max(0.0, rhoV * (h_room - h_amb))    # start-of-step trace
        else:
            p = {"Q_server": Q_srv}
            QCOOL[i] = 0.0

        zz = odeint(room.rhs, z, [0.0, dt_s], args=(state, p))
        z = list(zz[-1])
        T[i], PHI[i], X[i] = room.invert(*z)
        MODE[i] = state; QDEM[i] = Q_srv

    res = _summarise(season, t, T, PHI, X, MODE, QCOOL, QAC, QDEM, WCOMP, WFAN, COPR)
    res["ac_fan_undersized_steps"] = fan_under
    return res


def _count_starts(mode, label):
    return int(sum(1 for i in range(1, len(mode))
                   if mode[i] == label and mode[i - 1] != label))


def _summarise(season, t, T, PHI, X, MODE, QCOOL, QAC, QDEM, WCOMP, WFAN, COPR):
    dt_h = config.TIME_STEP_MIN / 60.0
    WEL = WCOMP + WFAN   # total instantaneous electrical draw, both equipment
    DP = room.dew_point_C(X)
    # Duration/energy-weighted quantities (frac_*, ac_min/vent_min/off_min,
    # E_ac_kWh/E_vent_kWh) must exclude index 0: T/PHI/X/MODE/WCOMP/WFAN[0] are
    # the INITIAL CONDITION at t=0, not the result of integrating over a real
    # 5-min step (that's index 1..N-1, N-1 = 288 genuine steps/day). Counting
    # index 0 too treats one instant as a whole extra step -- e.g. it always
    # inflates off_min by one TIME_STEP_MIN per day (the sim always starts in
    # OFF), since MODE[0] is the pre-control label, not a simulated interval.
    # T_min/T_max etc. (the reported extremes) are unaffected -- they ask what
    # value the room reached, including its legitimate starting state, so they
    # keep the full array.
    T_i, PHI_i, DP_i, MODE_i = T[1:], PHI[1:], DP[1:], MODE[1:]
    WCOMP_i, WFAN_i = WCOMP[1:], WFAN[1:]
    frac_T_recommended = np.mean((T_i >= config.T_RECOMMENDED_LOW_C) &
                                  (T_i <= config.T_RECOMMENDED_HIGH_C))
    frac_T_allowable = np.mean((T_i >= config.T_ALLOW_LOW_C) &
                                (T_i <= config.T_ALLOW_HIGH_C))
    frac_phi_allowable = np.mean((PHI_i >= config.PHI_ALLOW_LOW) &
                                  (PHI_i <= config.PHI_ALLOW_HIGH))
    frac_dp_recommended = np.mean((DP_i >= config.DP_RECOMMENDED_LOW_C) &
                                   (DP_i <= config.DP_RECOMMENDED_HIGH_C))
    frac_dp_allowable = np.mean((DP_i >= config.DP_ALLOW_LOW_C) &
                                 (DP_i <= config.DP_ALLOW_HIGH_C))
    return {
        "season": season, "t": t, "T": T, "phi": PHI, "X": X, "T_dp": DP, "mode": MODE,
        "Q_cool": QCOOL, "Q_AC": QAC, "Q_dem": QDEM,
        "W_el": WEL, "W_comp": WCOMP, "W_fan": WFAN, "COP_res": COPR,
        "T_min": float(T.min()), "T_max": float(T.max()),
        "phi_min": float(PHI.min()), "phi_max": float(PHI.max()),
        "dp_min": float(DP.min()), "dp_max": float(DP.max()),
        "frac_T_recommended": float(frac_T_recommended),
        "frac_T_allowable": float(frac_T_allowable),
        "frac_phi_allowable": float(frac_phi_allowable),
        "frac_dp_recommended": float(frac_dp_recommended),
        "frac_dp_allowable": float(frac_dp_allowable),
        "ac_starts": _count_starts(MODE, "AC"),
        "vent_starts": _count_starts(MODE, "VENT"),
        "ac_min": float(np.sum(MODE_i == "AC") * config.TIME_STEP_MIN),
        "vent_min": float(np.sum(MODE_i == "VENT") * config.TIME_STEP_MIN),
        "off_min": float(np.sum(MODE_i == "OFF") * config.TIME_STEP_MIN),
        # By EQUIPMENT (compressor vs fan), not by mode -- the fan also runs
        # during AC (shared ventilator drives the coil recirc flow), so a
        # mode-based split (sum WEL where MODE=="AC"/"VENT") would silently
        # drop that fan energy. E_ac_kWh = compressor only; E_vent_kWh = fan
        # only, correctly including its AC-mode contribution.
        "E_ac_kWh": float(np.sum(WCOMP_i) * dt_h),
        "E_vent_kWh": float(np.sum(WFAN_i) * dt_h),
    }

def simulate_all(cmap=None):
    if cmap is None:
        cmap = cycle.build_map()
    return {s: simulate_season(s, cmap) for s in config.SEASONS}
