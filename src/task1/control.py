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
# No-damper single-flow switch (Task-1 design EXPERIMENT; owned here so the whole
# experiment reverts by restoring control.py from its copy -- nothing else to undo).
#
# The two modes share ONE ventilator (the section-5 coupling constraint). WITH a
# damper/VFD that fan delivers TWO flows: a gentle design flow for free cooling
# (config.VENT_FLOW_DESIGN_M3S, sized so a single VENT step cannot overshoot the
# low band) and the much higher recirc flow the AC coil needs
# (flow_limits.ac_fan_flow_from_map, sized to hold the coil-outlet pinch above
# T_ev). WITHOUT a damper the fan has a SINGLE operating point, so both modes must
# run at the SAME flow.
#
#   VENT_USES_AC_FLOW = True  -> NO-DAMPER test: VENT is forced to the per-combo AC
#                                recirc flow. PHYSICS WARNING: at that flow the room
#                                time constant tau = M_air/(rho*V) collapses to ~1
#                                timestep, so one VENT step drives the room most of
#                                the way to ambient -> cold-season undershoot and
#                                chatter (verified: a single winter VENT step lands
#                                ~11 C at bore30, ~3 C at bore50). The two-setpoint
#                                staging in decide() is UNCHANGED -- only the flow.
#   VENT_USES_AC_FLOW = False -> baseline two-flow design (damper/VFD).
#
# simulation.py reads this via getattr(control, ...), so restoring the ORIGINAL
# control.py (which lacks these symbols) silently falls back to the two-flow baseline.
VENT_USES_AC_FLOW = False


def vent_flow_m3s(V_AC_fan, V_vent_design):
    """Operating ventilation flow under the single-ventilator coupling.
    decide() picks the MODE; this picks the FLOW that mode runs at. No damper
    (VENT_USES_AC_FLOW=True) -> VENT is forced to the AC recirc flow V_AC_fan;
    otherwise the gentle design flow V_vent_design."""
    return V_AC_fan if VENT_USES_AC_FLOW else V_vent_design


# ----------------------------------------------------------------------------
# Ambient-scheduled relay setpoints (Task-1 design EXPERIMENT; owned here, same
# revert-by-copy contract). In hot weather the compressor's mandatory standstill
# lets the room slew up uncooled (VENT cannot assist when ambient >= room); the
# peak is ~ T_OFF + Q_server * t_standstill / (M*cp). Shifting the WHOLE relay band
# DOWN in hot weather lowers that peak ~1:1 -> hard-limit (35 C) margin. It does
# NOT shrink the standstill swing (~8-14 K at peak load, wider than the 9 K
# recommended band), so it buys safety margin, not recommended-band compliance,
# and it does NOT help the cold-season single-flow VENT crash (that needs a lower
# flow, not a setpoint).
#
#   T_set(T_amb) = T_set0 - shift,  shift = SCHED_G + SCHED_K * max(0, T_amb - T*)
#   clamped so T_OFF never drops below SCHED_T_OFF_FLOOR (do not trade an upper
#   breach for a lower one). SCHED_G is a CONSTANT (ambient-independent) shift =
#   the "fixed-setpoint" arm of the tuning sweep; SCHED_K / SCHED_T_STAR are the
#   ambient ramp. SETPOINT_SCHEDULE = False -> decide() uses the config constants
#   unchanged (restoring control.py from its copy also fully reverts this).
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
