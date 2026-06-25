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
import numpy as np
from common import config, data_io


# --------------------------------------------------------------- Task 1.1
def required_cooling_power_kw(server_by_season):
    """Required cooling power = peak server load over all four days.

    The installed AC capacity is an OUTPUT of (bore, refrigerant), screened
    against this peak at the hottest ambient (capacity is weakest then);
    oversizing is penalised by part-load COP degradation (Task 3).
    """
    return float(max(np.max(s) for s in server_by_season.values()))


def design_peak_load_kw():
    """Rated (nameplate) peak server heat load, ~5 kW here. A fixed design
    number computed once from the server-load profile, NOT a live sensor
    reading -- the controller's only sensors are room/ambient temperature
    (see task1.control.vent_feasible), so it cannot see the actual
    instantaneous Q_demand and must size ventilation against the worst case
    instead."""
    server_raw, _ = data_io.load_raw()
    return float(np.max(server_raw))


Q_DESIGN_PEAK_KW = design_peak_load_kw()


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
    for dt in (5.0, 10.0, 13.0):
        print("          V_min at dT = {:>4.1f} K, peak load        = "
              "{:.2f} m3/s".format(dt, float(v_min_m3s(q_peak, dt))))
    print("          ventilation switch dT (V_min = V_max)     = "
          "{:.2f} K  (need T_amb < T_room - this)".format(
              ventilation_switch_dt_k(q_peak)))
    return q_peak, vmax
