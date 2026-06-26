"""
Central configuration for the server-room cooling model

UNIT CONVENTION
---------------
The course add-ons (Fluid_CP, Fluid_CP_moist_air, Eh="CBar") and the provided
compressor module all work in:
    temperature  : degC
    pressure     : bar
    enthalpy     : kJ/kg
    power / load : kW
    mass flow    : kg/s
    time         : s
Raw CoolProp (SI: Pa, K, J/kg) is NEVER called directly in this project; only
the course wrappers are used, so the whole model stays in the units above.
This deliberately avoids the degC/K and kJ/J boundary bugs.

Assumptions that are ours to own/justify are tagged  [ASSUMPTION]  and open
points still to resolve are tagged  [FLAG].
"""

# ----------------------------------------------------------- room geometry
ROOM_LENGTH_M = 10.0
ROOM_WIDTH_M = 6.0
ROOM_HEIGHT_M = 3.0
ROOM_VOLUME_M3 = ROOM_LENGTH_M * ROOM_WIDTH_M * ROOM_HEIGHT_M          # 180 m3

# Constant dry-air mass in the room (quasi-incompressible balance, p = 1 bar).
# rho_dry ~ 1.19 kg/m3 at 15 degC / 60 % RH  ->  m_air ~ 216 kg  (brief).
AIR_DENSITY_KG_M3 = 1.19
M_AIR_KG = AIR_DENSITY_KG_M3 * ROOM_VOLUME_M3                          # ~216 kg
CP_AIR_KJ_KGK = 1.006        # dry-air cp, for the sensible V_min estimate only

# ----------------------------------------------------------- initial state
T_INIT_C = 15.0
PHI_INIT = 0.60
P_BAR = 1.0

# ----------------------------------------------- acceptable room-air bands
# Two nested envelopes, RECOMMENDED (comfort/target) vs ALLOWABLE (hard
# safety limit, never to be crossed), per Bea's decision (2026-06-19).
# RECOMMENDED drives the on/off setpoints (T_OFF_C/T_ON_C below); ALLOWABLE
# is the wider pass/fail bound reported in plots and scored in Task 3.
T_RECOMMENDED_LOW_C = 18.0   # [ASSUMPTION] ASHRAE recommended envelope lower
T_RECOMMENDED_HIGH_C = 27.0  # [ASSUMPTION] ASHRAE recommended envelope upper
T_ALLOW_LOW_C = 10.0         # hard lower limit
T_ALLOW_HIGH_C = 35.0        # hard upper limit
# BUGFIX (found 2026-06-25): flow_limits.vent_overshoot_ok and simulation.py
# reference config.T_BAND_LOW_C, which was never defined after the RECOMMENDED/
# ALLOWABLE rename -> it AttributeErrors the instant the VENT-overshoot guard
# fires. The gentle baseline flow never trips it; single-flow trips it at once.
# Defined here = RECOMMENDED low (matches the sizing-derivation comment "(23.5-18)").
T_BAND_LOW_C = T_RECOMMENDED_LOW_C
T_BAND_HIGH_C = T_RECOMMENDED_HIGH_C

# Humidity is MONITORED, not controlled (no (de)humidifier actuator). The
# binding risk is the LOWER bound: AC condensation dries the room.
PHI_RECOMMENDED_LOW = 0.30   # comfort/target band lower
PHI_RECOMMENDED_HIGH = 0.70  # comfort/target band upper
PHI_ALLOW_LOW = 0.08         # hard lower limit
PHI_ALLOW_HIGH = 0.80        # hard upper limit

# --------------------------------------------- control (1.3) state machine
# Temperature-only on/off with hysteresis, both setpoints inside the band.
# TODO: check the delta of the bang bang controller is sufficient to prevent excessive cycling
T_OFF_C = 21.5               # all cooling switches OFF at/below this
T_ON_C = 23.5                # FREE COOLING (VENT) switches on at/above this
T_ON_AC_C = 25.0             # MECHANICAL COOLING (AC) setpoint, > T_ON_C. VENT is
                             # tried first in [T_ON_C, T_ON_AC_C); if free cooling
                             # cannot hold the room and T climbs to here, escalate to
                             # AC. [ASSUMPTION] T_ON + 1.5 K. This temperature-only
                             # staging REPLACES the old load-based VENT->AC test
                             # (the controller has no load sensor; the room
                             # temperature itself is the adequacy signal). Widen the
                             # T_ON..T_ON_AC gap if doomed VENT attempts churn the AC.
TIME_STEP_MIN = 5.0          # simulation timestep ("sufficiently accurrate" but maybe worth running a sensitivity analysis on this)
# TODO: "Typical minimal standstill and running times of air conditioning units" but check if there is further information on this
MIN_RUN_MIN = 5.0            # minimum run time      = 1 step
MIN_STANDSTILL_MIN = 10.0    # minimum standstill    = 2 steps

# ------------------------------------------------------ flow limits (1.2)
# Acoustic/comfort velocity cap = Beaufort 5 ("fresh breeze"), Lecture #11
# slides 34-35. Beaufort 5 = 8.0-10.7 m/s (29-38 km/h); use the upper edge as
# the not-to-exceed cap (above it = Beaufort 6, "strong breeze").
V_MAX_BEAUFORT5_M_S = 10.7
# Supply-opening face area. NOT given by the slides (they show 5 cm / 50 cm
# illustrative openings); ~0.5 m equivalent opening assumed.
# Resolved (ex.10 / Lecture 10): the course sizes a real ventilator by
# intersecting its blower curve with the duct pressure drop (Lockhart-Martinelli)
# -- it does NOT use this velocity cap. So Beaufort-5 stays only as the acoustic
# NOT-TO-EXCEED limit the task asks us to "consider"; the operating flow is a
# design variable (VENT_FLOW_DESIGN_M3S below), not this cap.
A_SUPPLY_M2 = 0.20           # [ASSUMPTION][FLAG] refine to make sure vmax <= 0.25
DELTA_T_SUPPLY_GUIDE_K = 10.0

# ----------------------------------------- ventilation DESIGN flow (1.2 / 1.3)
# The ventilator is ON/OFF at a SINGLE design flow. The task lists "ventilator
# volumetric flow rate" as a design variable and says to choose the ventilation
# cooling power "wisely to avoid undesirable temperature fluctuations", so the
# operating flow is NOT the acoustic cap above -- the cap is only an upper bound.


# Sizing rule (ours, justified). The room is ~1st-order toward ambient with
# time constant tau = M_air / (rho * V); one timestep closes a fraction
# f = 1 - exp(-dt/tau) of (T_room - T_amb). The worst single VENT step starts at
# T_ON and sees the coldest ambient (= 1 degC over the four days). Requiring that
# step to land at/above the lower band:
#     f <= (T_ON - T_BAND_LOW) / (T_ON - T_amb_min)
#        = (23.5 - 18) / (23.5 - 1) = 0.244
#   ->  tau >= 1070 s  ->  V <= 0.168 m3/s.
# We take 0.15 m3/s: the worst winter step ends ~18.5 degC (~0.5 K floor margin),
# ~14x below the 2.14 m3/s Beaufort-5 cap and within any plausible blower curve.
#
# Trade-off to OWN in the report: a flow this gentle carries only ~1-4 kW of free
# cooling at realistic dT, so ventilation now TRIMS the load and the AC carries
# the rest in mild weather (it is no longer "winter = pure free cooling").
#
# Basis & source: airflow follows the sensible balance Q = rho*V*cp*dT
# (flow_limits.v_min_m3s). ASHRAE TC9.9, "Thermal Guidelines for Data Processing
# Environments" (2021), sizes data-centre airflow to the IT load and the
# allowable inlet temperature rise -- not to a fixed air-change rate -- and
# defines the 18-27 degC recommended inlet envelope adopted for the band. (This
# replaces the air-changes-per-hour rule removed below, which is an IAQ fresh-air
# metric, not a heat-removal sizing basis.)
# ONE ventilator, TWO flows (single unit = the §5 coupling; a VFD or an intake
# DAMPER gives the two speeds). The duties don't overlap: free cooling needs the
# LOW flow (below, else a worst winter step overshoots the low band) while AC
# recirc needs a HIGH flow (else T_AC < T_ev + pinch).
#
# Only the LOW (vent) flow is a free design constant and lives here. The HIGH (AC
# recirc) flow is NOT a constant: it must carry the compressor's full on/off
# capacity, which scales ~bore^2, so a single number cannot be right for all three
# bores. It is therefore DERIVED per (bore, refrigerant) from that combo's capacity
# map in flow_limits.ac_fan_flow_from_map(), and the one-ventilator coupling
# (acoustic cap + vent->AC turndown) is checked in flow_limits.assert_ac_fan_feasible().
# (The removed AC_FAN_FLOW_M3S = 0.62 was bore30's number applied to every bore: it
# undersized bore40/50, pinned T_AC at the coil floor and corrupted the humidity track.)
VENT_FLOW_DESIGN_M3S = 0.15     # LOW: free cooling. Matches the tau/overshoot
                                # derivation above (was wrongly 0.30 -> overshot).

# AC-fan sizing ceiling: highest room temperature the recirc fan must serve.
# [ASSUMPTION] set to the worst control OVERSHOOT (~35 degC), NOT the band top. The
# on/off controller's standstill-lockout x slew-rate drives T_room to ~34.8 in the
# four-day sim (see overshoot analysis); the fan must keep its coil pinch THERE too
# or the coil floors (fan_under) mid-excursion. Sizing to this (vs band+2K) inflates
# V_AC ~25% and, by design, EXPOSES which bores can no longer be served within the
# Beaufort-5 acoustic cap / single-VFD turndown -> a Task-3 feasibility result, not a
# crash (check_ac_fan_feasible warns + clamps). Revert to ~T_BAND_HIGH_C + 2 if the
# overshoot is later tightened. NB observed max 34.8 -> 0.2 K margin; bump to 36 (map
# grid top) for headroom.
T_ROOM_MAX_DESIGN_C = 35.0
# TODO: [task 4] ventilation fan power depends on HOW the low flow is made: a damper
# throttles a fixed-speed fan (~near-full power at low flow) -> free cooling costs
# more; a VFD scales ~flow^3 -> free cooling near-free. Decide & justify.

# ------------------------------------------------- AC cycle (Task-1 stand-in)
# Subcritical VCC. Constant approach temperatures (also off-design):
#   T_ev = T_room - DT_APPROACH_EVAP_K     (source side)
#   T_co = T_amb  + DT_APPROACH_COND_K     (sink side)
# Air-side: air leaves the coil at  T_AC = T_ev + DT_APPROACH_AIR_K.
#
# [ASSUMPTION][FLAG] evaporator-approach magnitude = the key compromise.
#   To dehumidify (brief), the coil must sit BELOW the room dew point
#   (~7.3 degC at 15 degC / 60 %). With DT_APPROACH_AIR_K = 3 that needs
#   T_AC < 7.3  =>  T_ev < ~4.3  =>  DT_APPROACH_EVAP_K > ~11 K. A larger
#   approach also delivers the ~10 K supply dT the velocity cap wants, but it
#   LOWERS T_ev and therefore COP. This magnitude is exactly the
#   COP-vs-(dehumidification + comfort) trade-off the Task-2 inner optimisation
#   must resolve; here it is fixed as a defensible stand-in.
# TODO: corroborate with ex.3 to understand if we have to optimize it
DT_APPROACH_EVAP_K = 12.0    # -> T_ev = T_room - 12  (3 degC at 15 degC room)
DT_APPROACH_COND_K = 10.0    # [ASSUMPTION] realistic AIR-cooled approach: field ~7-12 K
                             # (Ex.3's 5.6 K was a WATER sink). Reverted from the merge's
                             # optimistic 5 K, which implies an oversized/high-eff condenser
                             # (lower lift -> higher COP than is realistic for air cooling).
DT_APPROACH_AIR_K = 3.0      # T_AC = T_ev + 3   (answer to setup question 3)
DELTA_T_SUPERHEAT_K = 5.0    # [ASSUMPTION] realistic suction superheat
DELTA_T_SUBCOOL_K = 5.0      # liquid leaves at T_co-5 = T_amb+5 (physical 5 K condenser
                             # cold-end pinch). Reverted from the merge's 0. NB COP rises
                             # MONOTONICALLY with subcool to the sink bound (superheat_subcool
                             # _sweep), so a FIXED 5 K is conservative, not the optimum.
                             # IGNORED by the compressor fn; affects q_evap / COP only, not
                             # m_dot or eta.
MIN_PRESSURE_RATIO = 2.0     # compressor envelope; binds at low ambient

# Pinch-point floors for cycle.optimize_cop: the minimum allowed approach
# temperature on each heat exchanger (T_room - T_ev and T_co - T_amb), i.e.
# how close the refrigerant may sit to the air stream before heat-exchanger
# area would need to go to infinity. [ASSUMPTION] 5 K each side.
PINCH_EVAP_K = 5.0           # floor on T_room - T_ev
PINCH_COND_K = 5.0           # floor on T_co - T_amb

# Stand-in (bore, refrigerant) for the Task-1 demonstration run.
# The full sweep over BORES x REFRIGERANTS is Task 3.
STANDIN_BORE_MM = 30.0       # [ASSUMPTION] 30 mm bore is the stand-in for the Task-1 demonstration run
STANDIN_REFRIGERANT = "Propane" # [ASSUMPTION] Propane is the stand-in for the Task-1 demonstration run

COMPRESSOR_BORES_MM = [30.0, 40.0, 50.0]
COMPRESSOR_N_CYL = 2         # RESOLVED (Moodle, L. Liebl 2026-06-11): the task's
                             # "4-cylinder" was a TYPO. The AC is a 2-cylinder
                             # compressor, exactly as recip_comp_corr_SP computes
REFRIGERANTS = ["Propane", "R1234yf", "DimethylEther"]   # exact CoolProp names

# Part-load degradation (Hint 2): COP_res = COP_inner * PLR / (0.9*PLR + 0.1)
PART_LOAD_A = 0.9
PART_LOAD_B = 0.1

# ---------------------------------------------------------- ventilation
VENT_AMBIENT_PHI = 0.60      # ambient air is 60 % RH (brief)

# --------------------------------------------------------- Task 4 economics
# [ASSUMPTION][FLAG] electricity tariff, CHF/kWh, ONE VALUE PER REPRESENTATIVE
# SEASON-DAY (not a single flat number): each season's energy is costed at
# that season's own price, since real tariffs vary seasonally (e.g. winter
# peak pricing). Region/provider is NOT given by the task sheet -- pick one
# and own it in the report (e.g. ewz Zurich, since this is an ETH project).
# Placeholder values below; replace with sourced figures before Task 4.
ELEC_PRICE_CHF_PER_KWH = {
    "winter": 0.27,
    "spring": 0.27,
    "summer": 0.27,
    "fall": 0.27,
}

# [ASSUMPTION] combined compressor motor + drive efficiency, converting the
# compressor model's FLUID/shaft power (W = m_dot*(h2-h1), from
# recip_comp_corr_SP -- see notes/Compressor_Model_Bridge.md, point P7) to the
# electrical power actually billed:  P_elec = P_fluid / ETA_MOTOR_ELEC.
# The course's Ex.6 simplification is ETA_MOTOR_ELEC = 1.0 (P_elec ~= P_fluid);
# we instead own a realistic combined hermetic-motor + drive efficiency for a
# small reciprocating unit. Set to 1.0 to fall back to the course shortcut.
# The ventilation fan's power (FAN_SPECIFIC_POWER_KW_PER_M3S in task1.simulation)
# is already an electrical stand-in -- it is NOT divided by this.
ETA_MOTOR_ELEC = 0.90

# Each representative season-day stands for one quarter of the year (the four
# days together cover winter/spring/summer/fall). [ASSUMPTION] no within-
# season variation beyond the single representative day is captured.
DAYS_PER_REPRESENTATIVE_SEASON = 365.25 / 4.0

# ---------------------------------------------------------- input data
SEASONS = ["winter", "spring", "summer", "fall"]
FILE_AMBIENT = {s: "data/ambient_temperature_{}.txt".format(s) for s in SEASONS}
FILE_SERVER_HEAT = "data/server_heating_power.txt"
# Each input file holds 48 values per representative season-day.
# [ASSUMPTION][FLAG] 48 pts over 24 h => 30-min sampling; day treated periodic.
DATA_POINTS_PER_DAY = 48
DATA_RESOLUTION_MIN = 30.0
DAY_MIN = 24.0 * 60.0

# --------------------------------------------------- Task 2 map output (I/O)
PERFORMANCE_MAP_DIR = "results"   # precomputed (T_room,T_amb) AC maps, per (refrigerant, bore)

# --------------------------------------------------------- ETH colour scheme
# ETH Zurich corporate identity palette. Used consistently across every plot
# in common/plotting.py and the Task-2 optimizer diagnostics in
# task2/cycle_opt.py (the diverging map there is ETH Blue <-> white <-> ETH
# Red, replacing an earlier colour-blind-safe Okabe-Ito choice for brand
# consistency -- NB this trades away that specific accessibility property).
ETH_BLUE = "#215CAF"
ETH_PETROL = "#007894"
ETH_GREEN = "#627313"
ETH_BRONZE = "#8E6713"
ETH_RED = "#B7352D"
ETH_PURPLE = "#A7117A"
ETH_GREY = "#6F6F6F"

# Semantic roles -- plotting.py reads what a colour MEANS, not a raw hex/
# matplotlib name, so the mapping only has to be decided once, here.
COLOR_ROOM_T = ETH_BLUE
COLOR_ROOM_RH = ETH_PURPLE
COLOR_HUMIDITY_RATIO = ETH_PETROL
COLOR_AC = ETH_BLUE                  # compressor: duty cycle, energy, starts, cost
COLOR_VENT = ETH_GREEN               # ventilation/fan: duty cycle, energy, starts, cost
COLOR_OFF = ETH_GREY                 # neutral: OFF duty-cycle segment
COLOR_SERVER_LOAD = ETH_RED
COLOR_COOLING_DELIVERED = ETH_BLUE
COLOR_RECOMMENDED_BAND = ETH_GREEN   # comfort/target band shading (T and RH)
COLOR_ALLOWABLE_LIMIT = ETH_RED      # hard safety-limit lines (T and RH)
COLOR_SETPOINT = ETH_GREY            # ON/OFF hysteresis setpoint lines
COLOR_SELECTED_DESIGN = ETH_BRONZE   # Task-3-selected design highlight outline
COLOR_NEUTRAL = ETH_GREY             # reference lines, contour overlays, etc.

# One colour per representative season-day (winter/spring/summer/fall),
# shared across plot_overview and any other multi-season figure.
SEASON_COLORS = {"winter": ETH_BLUE, "spring": ETH_GREEN,
                 "summer": ETH_RED, "fall": ETH_BRONZE}
