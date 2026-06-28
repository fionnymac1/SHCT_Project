"""
Task 1.3 control - temperature-only on/off state machine.

  * hysteresis & staging: free cooling (VENT) switches on at T_ON_C, mechanical
    cooling (AC) at the higher T_ON_AC_C, all cooling off at T_OFF_C; inside a
    deadband the current mode is held.
  * free-cooling-first: when cooling is needed try VENT first; if it cannot hold
    the room and T climbs to T_ON_AC_C, escalate to AC. Decided on TEMPERATURE
    ONLY (no load sensor) -- the room temperature is the adequacy signal.
  * vent-assist: while the compressor is in its mandatory standstill it is OFF,
    so the shared fan is otherwise idle -> if ambient is below the room, run VENT
    for PARTIAL cooling to trim the rise (vent_available). The compressor stays
    off, so AC and VENT are never simultaneous; the single fan still does one job.
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

MIN_RUN_STEPS = max(1, math.ceil(config.MIN_RUN_MIN / config.TIME_STEP_MIN))
MIN_STANDSTILL_STEPS = max(1, math.ceil(
    config.MIN_STANDSTILL_MIN / config.TIME_STEP_MIN))


# ----------------------------------------------------------------------------
# Single-flow alternative (tested, not adopted -- see "two flows on one
# ventilator" in the report). With a damper/VFD the shared fan delivers two
# flows: gentle for free cooling, high for AC recirculation. Without one, both
# modes share a single operating point. VENT_USES_AC_FLOW=True forces VENT
# onto the AC recirc flow, collapsing the room's time constant to ~1 step and
# causing cold-season undershoot/chatter -- the experiment that justified
# keeping the two-flow design.
VENT_USES_AC_FLOW = False


def vent_flow_m3s(V_AC_fan, V_vent_design):
    """Operating ventilation flow: the AC recirc flow if VENT_USES_AC_FLOW
    (no-damper test), else the gentle design flow."""
    return V_AC_fan if VENT_USES_AC_FLOW else V_vent_design


# ----------------------------------------------------------------------------
# Ambient-scheduled relay setpoints (the placement search behind the report's
# "Setpoint placement" sensitivity figure). T_set(T_amb) = T_set0 - shift,
# shift = SCHED_G + SCHED_K*max(0, T_amb - T*), clamped so T_OFF never drops
# below SCHED_T_OFF_FLOOR. SCHED_G is the adopted flat shift (1 K); SCHED_K/
# SCHED_T_STAR are an (unused, K=0) ambient-ramp alternative that was tested
# and didn't improve on the flat shift.
SETPOINT_SCHEDULE = True
SCHED_G = 1.0             # constant downward shift of the whole relay band [K]
SCHED_K = 0.0             # extra downward shift per K of ambient above T* [K/K]
SCHED_T_STAR = 24.0       # ambient breakpoint for the ramp [degC]
SCHED_T_OFF_FLOOR = 18.0  # T_OFF floor (= recommended-band low); shift clamped to it


def setpoints(T_amb):
    """(T_OFF, T_ON, T_ON_AC) for this ambient. Schedule off -> the config
    constants unchanged. On -> shifts the whole band down rigidly (deadband widths
    and ordering preserved), clamped so T_OFF >= SCHED_T_OFF_FLOOR."""
    if not SETPOINT_SCHEDULE:
        return config.T_OFF_C, config.T_ON_C, config.T_ON_AC_C
    shift = SCHED_G + SCHED_K * max(0.0, T_amb - SCHED_T_STAR)
    shift = max(0.0, min(shift, config.T_OFF_C - SCHED_T_OFF_FLOOR))
    return config.T_OFF_C - shift, config.T_ON_C - shift, config.T_ON_AC_C - shift


def vent_available(T_room, T_amb):
    """Free cooling usable: ambient is below the room, so pushing ambient air
    removes heat. This temperature-only test is THE gate for VENT now -- both as
    the primary free-cooling mode (decide tries it first at T_ON_C) and as the
    standstill assist. Whether the gentle design flow carries the FULL load is NOT
    predicted; if it cannot, the room climbs to T_ON_AC_C and decide() escalates
    to AC."""
    return T_amb < T_room - 0.5


def decide(state, comp_run_steps, comp_idle_steps, T_room, T_amb):
    """Next mode in {OFF, VENT, AC} from TEMPERATURES ONLY (no load sensing).
    Two cooling setpoints stage free cooling below mechanical cooling:
      * T_ON_C    -> try free cooling (VENT) first;
      * T_ON_AC_C -> if VENT cannot hold the room and T climbs to here, escalate
                     to the compressor (AC);
      * T_OFF_C   -> stop all cooling.
    The room temperature is itself the adequacy signal: if VENT keeps up, T never
    reaches T_ON_AC_C, so the load never has to be known. comp_run_steps /
    comp_idle_steps gate only AC transitions (compressor min-run / standstill);
    the blower switches freely."""
    T_off, T_on, T_on_ac = setpoints(T_amb)       # ambient-scheduled (or constants)
    want_off = T_room <= T_off
    need_cool = T_room >= T_on                     # free-cooling stage
    need_ac = T_room >= T_on_ac                    # VENT could not hold -> mechanical
    va = vent_available(T_room, T_amb)

    if state == "AC":
        # min-run before the compressor may stop, then run it down to T_OFF. No
        # mid-run hand-back to VENT: AC only engaged because VENT already failed to
        # hold the room, so ambient is not cold enough to hand back to.
        if comp_run_steps < MIN_RUN_STEPS:
            return "AC"
        if want_off:
            return "OFF"
        return "AC"

    # fan-only states (OFF / VENT): no cycling limit on the blower
    if need_ac:
        # free cooling could not hold the room (T reached the AC setpoint)
        if comp_idle_steps >= MIN_STANDSTILL_STEPS:
            return "AC"               # compressor available -> mechanical cooling
        # Compressor still in its mandatory standstill (locked OFF). The shared fan
        # is otherwise idle, so use it for PARTIAL free cooling to trim the rise
        # instead of letting the room run away to the standstill peak; the
        # compressor stays off, so AC and VENT remain non-simultaneous.
        return "VENT" if va else state
    if need_cool:
        # free-cooling band [T_ON_C, T_ON_AC_C): try the blower first
        if va:
            return "VENT"             # free-cooling-first
        if comp_idle_steps >= MIN_STANDSTILL_STEPS:
            return "AC"               # ambient too warm for free cooling -> mechanical
        return state                  # compressor locked & no free cooling -> hold
    if want_off:
        return "OFF"
    if state == "VENT" and not va:
        return "OFF"                  # ambient no longer cold enough
    return state
