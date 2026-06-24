"""
Task 1.1 - required cooling power.
Task 1.2 - volumetric flow limits and the ventilation mode-switch threshold.

Flow-cap basis (Lecture #11, slides 33-35):
  * The supply-air VELOCITY is the binding limit, capped at Beaufort 5
    ("fresh breeze"), because the room air must not feel windier than that.
  * V_max = v_Beaufort5 * A_supply.
  * To respect the cap you need a large enough supply temperature difference
    ("a minimum dT of ~10 K"), which trades against COP -> see cycle module.

All powers in kW, flows in m3/s, temperatures in degC/K.
"""
import warnings
import numpy as np
from common import config


# --------------------------------------------------------------- Task 1.1
def required_cooling_power_kw(server_by_season):
    """Required cooling power = peak server load over all four days.

    The installed AC capacity is an OUTPUT of (bore, refrigerant), screened
    against this peak at the hottest ambient (capacity is weakest then);
    oversizing is penalised by part-load COP degradation (Task 3).
    """
    return float(max(np.max(s) for s in server_by_season.values()))


# --------------------------------------------------------------- Task 1.2
def v_max_acoustic_m3s():
    """Acoustic/comfort flow cap = Beaufort-5 face velocity x supply area.
    UPPER BOUND only (the task's "acoustic and flow velocity constraint"),
    not the operating flow."""
    return config.V_MAX_BEAUFORT5_M_S * config.A_SUPPLY_M2


def vent_flow_design_m3s():
    """ON/OFF ventilator operating flow (single design speed), set in config.
    This is what the fan actually delivers when VENT is on. It is sized (see
    config.VENT_FLOW_DESIGN_M3S) so one timestep of free cooling cannot overshoot
    the lower band, and must stay <= v_max_acoustic_m3s()."""
    return config.VENT_FLOW_DESIGN_M3S


def v_min_m3s(q_kw, dt_k):
    """Minimum volume flow to carry load q_kw at sensible difference dt_k:
        V_min = Q / (rho * cp * dT).
    For ventilation dt_k = T_room - T_amb; for AC dt_k = T_room - T_AC.
    """
    dt_k = np.asarray(dt_k, dtype=float)
    out = q_kw / (config.AIR_DENSITY_KG_M3 * config.CP_AIR_KJ_KGK * dt_k)
    return out


def ventilation_switch_dt_k(q_kw):
    """Smallest (T_room - T_amb) for which free cooling can carry q_kw within
    the acoustic cap, i.e. the dT where V_min(dT) = V_max.
        dT_switch = Q / (rho * cp * V_max).
    Free cooling is usable when ambient is colder than the room by at least
    this margin (and, trivially, when T_amb < T_room).
    """
    return q_kw / (config.AIR_DENSITY_KG_M3 * config.CP_AIR_KJ_KGK
                   * v_max_acoustic_m3s())


def ac_fan_flow_m3s(q_ac_max_kw, dt_air_k=None):
    """AC recirculation flow to carry the AC's FULL (on/off) capacity while keeping
    the coil-outlet air a pinch above the evaporating temperature:
        T_room - T_AC <= EVAP - AIR   ->   V >= q / (rho*cp*(EVAP-AIR)).
    Size on the MAX Q_AC the chosen bore delivers when ON (not q_peak), so the air
    approach stays >= AIR everywhere. dt_air_k defaults to EVAP-AIR (= 9 K)."""
    if dt_air_k is None:
        dt_air_k = config.DT_APPROACH_EVAP_K - config.DT_APPROACH_AIR_K
    return q_ac_max_kw / (config.AIR_DENSITY_KG_M3 * config.CP_AIR_KJ_KGK * dt_air_k)


def ac_fan_flow_from_map(cmap, t_room_hi_C=None):
    """Per-combo AC recirculation flow, DERIVED from THIS map's capacity (it is not
    a config constant). Size the fan to the largest Q_AC the compressor delivers
    over the region the room actually occupies while the AC runs, so the coil-outlet
    air keeps its >= AIR pinch above T_ev (T_room - T_AC <= EVAP - AIR) at every
    on-step. Capacity ~ bore^2, so this is bore-specific by construction -- which is
    exactly why one number in config cannot be right for all three bores.

    Operating window T_room in [T_OFF, t_room_hi]; t_room_hi defaults to
    T_ROOM_MAX_DESIGN_C = the worst control OVERSHOOT the fan must serve (~35 degC),
    NOT the band top: the on/off controller runs the room well above the band (T_max
    ~34.8 in the four-day sim), and the fan must hold its coil pinch there too or the
    coil floors mid-excursion (fan_under). Q_AC rises with T_room and toward cold
    ambient (where the min-pressure-ratio clamp may cap it), so the max is taken over
    the FULL ambient grid; nanmax is robust to the clamp. Sizing to this ceiling
    inflates V_AC and pushes the largest bores against the acoustic cap / turndown
    (check_ac_fan_feasible warns + clamps) -- a deliberate feasibility result.
    Returns (V_AC_m3s, Q_AC_max_kW)."""
    if t_room_hi_C is None:
        t_room_hi_C = config.T_ROOM_MAX_DESIGN_C
    Tr = np.asarray(cmap["T_room_grid"], dtype=float)
    Q = np.asarray(cmap["Q_AC"], dtype=float)
    sel = (Tr >= config.T_OFF_C) & (Tr <= t_room_hi_C)
    if not sel.any():                       # window outside the grid -> size on all
        sel = np.ones_like(Tr, dtype=bool)
    q_ac_max = float(np.nanmax(Q[sel, :]))
    return ac_fan_flow_m3s(q_ac_max), q_ac_max


def check_ac_fan_feasible(V_sized_m3s, max_turndown=10.0):
    """Diagnose the single-ventilator coupling for the AC recirc duty (replaces the
    old per-condition spot checks). Returns (V_used, turndown, clamped):

      * V_used = the sized flow CAPPED at the Beaufort-5 acoustic limit -- you
        physically cannot push more than that through the supply grille. If the cap
        binds, the coil floors on the hottest on-steps and the sim's fan_under
        counter records it (graceful degradation, a Task-3 result, not a crash).
      * turndown = V_used / VENT_FLOW_DESIGN -- the span one ventilator must cover.

    WARNS (never raises) so the Task-3 sweep keeps every candidate, when
        (a) the acoustic cap clamps the flow, or
        (b) the vent->AC turndown exceeds a typical single VFD's ~max_turndown:1."""
    vmax = v_max_acoustic_m3s()
    V_used = min(V_sized_m3s, vmax)
    clamped = V_sized_m3s > vmax + 1e-9
    if clamped:
        warnings.warn("AC recirc flow %.2f m3/s exceeds the Beaufort-5 acoustic cap "
                      "%.2f m3/s; clamped -> coil will floor on the hottest steps "
                      "(see fan_under)." % (V_sized_m3s, vmax))
    turndown = V_used / config.VENT_FLOW_DESIGN_M3S
    if turndown > max_turndown + 1e-9:
        warnings.warn("vent->AC turndown %.1fx exceeds a typical single VFD's "
                      "~%.0f:1 range; needs a premium VFD or a damper assist for "
                      "this bore." % (turndown, max_turndown))
    return V_used, turndown, clamped


def vent_step_landing_C(V_flow_m3s, T0_C, T_amb_C, q_server_kw, dt_min=None):
    """Room temperature after one VENT step (lumped sensible balance incl. server):
        M*cp*dT/dt = q_server - rho*V*cp*(T - T_amb)  ->  first order toward T_eq.
    Used to size the free-cooling flow so it cannot overshoot the low band."""
    if dt_min is None:
        dt_min = config.MIN_RUN_MIN
    rhoVcp = config.AIR_DENSITY_KG_M3 * V_flow_m3s * config.CP_AIR_KJ_KGK
    tau = config.M_AIR_KG * config.CP_AIR_KJ_KGK / rhoVcp
    T_eq = T_amb_C + q_server_kw / rhoVcp
    return T_eq + (T0_C - T_eq) * np.exp(-dt_min * 60.0 / tau)


def vent_overshoot_ok(V_flow_m3s, T_amb_min_C, q_server_min_kw):
    """Worst forced VENT step (min run, from T_ON, coldest ambient, lowest server)
    must land at/above the lower band. Returns (T_land, ok)."""
    T_land = vent_step_landing_C(V_flow_m3s, config.T_ON_C, T_amb_min_C, q_server_min_kw)
    return T_land, (T_land >= config.T_BAND_LOW_C)


def summarise(server_by_season):
    """Print the Task 1.1/1.2 headline numbers."""
    q_peak = required_cooling_power_kw(server_by_season)
    vmax = v_max_acoustic_m3s()
    print("Task 1.1  required cooling power (peak server load) = "
          "{:.2f} kW".format(q_peak))
    print("Task 1.2  V_max (Beaufort 5 x {:.2f} m2)            = "
          "{:.2f} m3/s".format(config.A_SUPPLY_M2, vmax))
    vdes = vent_flow_design_m3s()
    tau = config.M_AIR_KG / (config.AIR_DENSITY_KG_M3 * vdes)
    print("          V_design (on/off ventilator)             = "
          "{:.3f} m3/s ({:.0f}% of cap)".format(vdes, 100.0 * vdes / vmax))
    print("          room tau = M/(rho*V_design)              = "
          "{:.0f} s = {:.1f} steps".format(tau, tau / (config.TIME_STEP_MIN * 60.0)))
    dtg = config.DELTA_T_SUPPLY_GUIDE_K
    print("          V_min at design dT = {:>4.1f} K, peak load   = "
          "{:.2f} m3/s".format(dtg, float(v_min_m3s(q_peak, dtg))))
    print("          ventilation switch dT (V_min = V_max)     = "
          "{:.2f} K  (need T_amb < T_room - this)".format(
              ventilation_switch_dt_k(q_peak)))
    return q_peak, vmax
