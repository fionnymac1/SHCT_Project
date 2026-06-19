"""
Task 1.3 control - temperature-only on/off state machine.

  * hysteresis: cooling switches ON at/above T_ON_C, OFF at/below T_OFF_C;
    inside the deadband the current mode is held.
  * free-cooling-first: when cooling is needed, use VENT if ambient can carry
    the load within the acoustic flow cap, else AC.
  * modes {OFF, VENT, AC} are mutually exclusive (one shared fan).
  * minimum run = 1 step (5 min); minimum standstill = 2 steps (10 min):
    a cooling mode must persist >= min-run before changing; OFF must persist
    >= min-standstill before cooling may restart (anti short-cycling).
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


def decide(state, steps_in_state, T_room, T_amb, Q_demand):
    """Return the next mode in {OFF, VENT, AC}."""
    # 1. minimum-run lock on an active cooling mode
    if state in ("AC", "VENT") and steps_in_state < MIN_RUN_STEPS:
        return state
    # 2. minimum-standstill lock on OFF
    if state == "OFF" and steps_in_state < MIN_STANDSTILL_STEPS:
        return state
    # 3. hysteresis
    if T_room >= config.T_ON_C:
        return "VENT" if vent_feasible(T_room, T_amb, Q_demand) else "AC"
    if T_room <= config.T_OFF_C:
        return "OFF"
    # 4. deadband: hold, but drop VENT if ambient is no longer cold enough
    if state == "VENT" and not vent_feasible(T_room, T_amb, Q_demand):
        return "AC"
    return state
