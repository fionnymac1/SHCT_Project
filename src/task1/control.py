"""
Task 1.3 control - temperature-only on/off state machine.

  * hysteresis: cooling switches ON at/above T_ON_C, OFF at/below T_OFF_C;
    inside the deadband the current mode is held.
  * free-cooling-first: when cooling is needed, use VENT if ambient can carry
    the load within the acoustic flow cap, else AC.
  * modes {OFF, VENT, AC} are mutually exclusive (one shared fan).
  * minimum run = 1 step (5 min); minimum standstill = 2 steps (10 min) apply
    to the COMPRESSOR ONLY. The task gives these as limits "of air conditioning
    units" - they model compressor pressure-equalisation (standstill) and oil
    return (run). A free-cooling blower has neither, so VENT and OFF (fan-only
    states) switch freely each step; the standstill clock counts time since the
    compressor last ran, including any intervening VENT.
"""
import math
from common import config
from task1 import flow_limits

MIN_RUN_STEPS = max(1, math.ceil(config.MIN_RUN_MIN / config.TIME_STEP_MIN))
MIN_STANDSTILL_STEPS = max(1, math.ceil(
    config.MIN_STANDSTILL_MIN / config.TIME_STEP_MIN))


def vent_feasible(T_room, T_amb, Q_demand):
    """Free cooling usable: ambient cooler than the room and the required flow
    within the Beaufort-5 acoustic cap."""
    if T_amb >= T_room - 0.5:
        return False
    return flow_limits.v_min_m3s(Q_demand, T_room - T_amb) <= \
        flow_limits.v_max_acoustic_m3s()


def decide(state, comp_run_steps, comp_idle_steps, T_room, T_amb, Q_demand):
    """Next mode in {OFF, VENT, AC}. comp_run_steps = steps the compressor has
    run continuously; comp_idle_steps = steps since it last ran (counts OFF and
    VENT alike). Compressor min-run/standstill gate only AC transitions; the fan
    switches freely."""
    want_cool = T_room >= config.T_ON_C
    want_off = T_room <= config.T_OFF_C
    vf = vent_feasible(T_room, T_amb, Q_demand)

    if state == "AC":
        # compressor must run >= min-run before it may stop
        if comp_run_steps < MIN_RUN_STEPS:
            return "AC"
        if want_off:
            return "OFF"
        if vf:
            return "VENT"          # free cooling now available -> drop compressor
        return "AC"

    # fan-only states (OFF / VENT): no cycling limit on the blower
    if want_cool:
        if vf:
            return "VENT"          # free-cooling-first
        # compressor needed: only if standstill (pressure equalisation) is met,
        # else hold and let the room keep rising until it clears
        return "AC" if comp_idle_steps >= MIN_STANDSTILL_STEPS else state
    if want_off:
        return "OFF"
    if state == "VENT" and not vf:
        return "OFF"               # ambient no longer cold enough
    return state
