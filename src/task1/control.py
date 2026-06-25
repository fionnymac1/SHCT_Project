"""
Task 1.3 control - temperature-only on/off state machine.

  * hysteresis: cooling switches ON at/above T_ON_C, OFF at/below T_OFF_C;
    inside the deadband the current mode is held.
  * free-cooling-first: when cooling is needed, use VENT if the design flow can
    carry the worst-case (design-peak) load at the current dT (vent_feasible),
    else AC -- the unit has no load sensor, only temperature, so feasibility is
    judged against the fixed design-peak load rather than the live Q_demand.
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
from task1 import flow_limits

MIN_RUN_STEPS = max(1, math.ceil(config.MIN_RUN_MIN / config.TIME_STEP_MIN))
MIN_STANDSTILL_STEPS = max(1, math.ceil(
    config.MIN_STANDSTILL_MIN / config.TIME_STEP_MIN))


def vent_available(T_room, T_amb):
    """Free cooling PHYSICALLY possible: ambient is below the room, so pushing
    ambient air removes heat -- regardless of whether the design flow can carry
    the FULL load. Used for the vent-assist stopgap during the compressor
    standstill (a partial-cooling role), distinct from vent_feasible below."""
    return T_amb < T_room - 0.5


def vent_feasible(T_room, T_amb):
    """Free cooling usable as the PRIMARY mode: ambient below the room AND the
    fixed design flow can carry the load at this dT. The unit has only
    temperature sensors -- no heat-load metering -- so the live Q_demand is
    unobservable to the controller; instead this checks against the fixed
    DESIGN PEAK load (flow_limits.Q_DESIGN_PEAK_KW, ~5 kW), i.e. the worst case
    the room can ever see. Vent is approved if and only if it could cover that
    peak at the current dT, which guarantees it can also cover the actual
    (smaller-or-equal, unmeasured) load -- a temperature-only, conservative
    stand-in for the load-aware test. Under on/off the ventilator runs at a
    single design speed, so the test compares the peak load against what THAT
    flow removes (V_min <= V_design) -- not against the acoustic cap. (The cap
    still bounds V_design itself; see config.VENT_FLOW_DESIGN_M3S.)"""
    if not vent_available(T_room, T_amb):
        return False
    return flow_limits.v_min_m3s(flow_limits.Q_DESIGN_PEAK_KW, T_room - T_amb) <= \
        config.VENT_FLOW_DESIGN_M3S


def decide(state, comp_run_steps, comp_idle_steps, T_room, T_amb):
    """Next mode in {OFF, VENT, AC}. comp_run_steps = steps the compressor has
    run continuously; comp_idle_steps = steps since it last ran (counts OFF and
    VENT alike). Compressor min-run/standstill gate only AC transitions; the fan
    switches freely."""

    want_cool = T_room >= config.T_ON_C
    want_off = T_room <= config.T_OFF_C
    vf = vent_feasible(T_room, T_amb)

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
            return "VENT"          # free-cooling-first (vent carries the full load)
        if comp_idle_steps >= MIN_STANDSTILL_STEPS:
            return "AC"            # compressor available -> use it
        # Compressor still in its mandatory standstill (locked OFF). The shared
        # fan is otherwise idle, so use it for PARTIAL free cooling to trim the
        # rise instead of letting the room run away to the standstill peak.
        # Only reached when vf is False (V_min > V_design) -> equilibrium temp is
        # above T_room, so the assist can only SLOW the climb, never over-cool.
        # Compressor stays off -> AC and VENT remain non-simultaneous.
        if vent_available(T_room, T_amb):
            return "VENT"
        return state              # no free cooling either -> hold until lockout clears
    if want_off:
        return "OFF"
    if state == "VENT" and not vf:
        return "OFF"               # ambient no longer cold enough
    return state
