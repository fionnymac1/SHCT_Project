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
# binding risk is the LOWER bound: AC condensation dries the room. Allowable
# only -- no separate recommended target (dew point carries the comfort
# target instead, see below).
PHI_ALLOW_LOW = 0.08         # hard lower limit
PHI_ALLOW_HIGH = 0.80        # hard upper limit

# Dew point: both bands. [ASSUMPTION] rationale not specified alongside the
# values -- these read as the same family of limit as ASHRAE TC9.9's
# data-centre envelopes (condensation risk above the upper bound,
# electrostatic-discharge/static risk below the lower bound), matching how
# T_RECOMMENDED/PHI_ALLOW are sourced elsewhere in this file. Computed from X
# via room.dew_point_C (Magnus-Tetens formula).
DP_RECOMMENDED_LOW_C = -9.0
DP_RECOMMENDED_HIGH_C = 15.0
DP_ALLOW_LOW_C = -9.0
DP_ALLOW_HIGH_C = 17.0

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
# Real day-ahead electricity prices (ENTSO-E Transparency Platform, Swiss
# bidding zone BZN|CH, EUR/MWh, hourly), one real calendar day per
# representative season -- NOT a flat assumed tariff. Each file's date is
# read back from its own MTU column (see data_io.load_dayahead_prices); the
# mapping below only has to say which file goes with which season.
FILE_DAYAHEAD_PRICES = {
    "winter": "data/GUI_ENERGY_PRICES_202512112300-202512122300.csv",
    "spring": "data/GUI_ENERGY_PRICES_202603112300-202603122300.csv",
    "summer": "data/GUI_ENERGY_PRICES_202606112200-202606122200.csv",
    "fall": "data/GUI_ENERGY_PRICES_202509112200-202509122200.csv",
}
# [ASSUMPTION] EUR->CHF spot conversion (ballpark 2025/26 rate; the day-ahead
# files are EUR/MWh). Revisit with the actual rate on each price date for a
# tighter number.
EUR_TO_CHF = 0.95

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

# ------------------------------------------------------------ figure output
# Single project-wide resolution for every saved figure (plotting.py reads
# this instead of each function hardcoding its own dpi), so main_plots.py's
# DPI knob actually controls all of them at once.
FIGURE_DPI = 400

# ------------------------------------------------------- ETH colour scheme
# Both the categorical (qualitative) and continuous (sequential) palettes
# below come from eth_colormaps -- one ETH-branded source of truth instead of
# the old Okabe-Ito accessibility palette. Import first; both sections need it.
from common import eth_colormaps

# Qualitative (discrete: lines/bars/bands) palette -- eth_colormaps.ETH_QUAL,
# used consistently across every plot in common/plotting.py. NOT for
# contour/heatmap data; see the sequential colormaps below for that.
ETH_QUAL_BLACK = eth_colormaps.ETH_QUAL["Black"]
ETH_QUAL_BLUE = eth_colormaps.ETH_QUAL["Blue"]
ETH_QUAL_PETROL = eth_colormaps.ETH_QUAL["Petrol"]
ETH_QUAL_GREEN = eth_colormaps.ETH_QUAL["Green"]
ETH_QUAL_GOLD = eth_colormaps.ETH_QUAL["Gold"]
ETH_QUAL_RED = eth_colormaps.ETH_QUAL["Red"]
ETH_QUAL_PURPLE = eth_colormaps.ETH_QUAL["Purple"]
ETH_QUAL_GREY = eth_colormaps.ETH_QUAL["Grey"]

# Semantic roles -- plotting.py reads what a colour MEANS, not a raw hex/
# matplotlib name, so the mapping only has to be decided once, here. Matches
# plot_season's role mapping (its own local block, see plotting.py) so every
# OTHER figure reads consistently with it:
#   Black = the controlled variable (room T) | Grey = neutral/off/secondary data
#   Blue  = the cooling system (AC)          | Purple = ventilation (VENT)
#   Red   = the heat source (server load)    | Green = comfort/allowable bands
COLOR_ROOM_T = ETH_QUAL_BLACK
COLOR_ROOM_RH = ETH_QUAL_GREY
COLOR_DEW_POINT = ETH_QUAL_GREY               # dew point trace (band shading is COLOR_HUMIDITY_BAND)
COLOR_AC = ETH_QUAL_BLUE             # compressor: duty cycle, energy, starts, cost
COLOR_VENT = ETH_QUAL_GOLD         # ventilation/fan: duty cycle, energy, starts, cost
COLOR_OFF = ETH_QUAL_BLACK            # neutral: OFF duty-cycle segment
COLOR_RECOMMENDED_BAND = ETH_QUAL_GREEN       # comfort/target + hard-limit band shading (T only);
                                               # allowable uses the paired companion shade below
COLOR_HUMIDITY_BAND = ETH_QUAL_PURPLE          # comfort/target + hard-limit band shading (RH, dew point)
COLOR_SELECTED_DESIGN = ETH_QUAL_GOLD         # Task-3-selected design highlight outline
COLOR_NEUTRAL = ETH_QUAL_BLACK                # reference lines, contour overlays, etc.

# Recommended/allowable are nested two-tier categories (inner comfort target
# vs outer hard limit). EVERY band now uses the paired companion shade
# (eth_colormaps.ETH_QUAL_PARTNER) for its outer/allowable tier instead of the
# same hue at a lower alpha -- a literal colour pair, not an opacity trick.
# RH has no recommended target of its own, so its one band uses the PURPLE
# partner shade too (the same one dew point's allowable tier uses), reading
# as "the allowable/outer tier of the humidity-band family" rather than a
# washed-out allowable of a colour that has no corresponding recommended band.
COLOR_RECOMMENDED_BAND_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Green"]    # T band, outer tier
COLOR_ROOM_T_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Black"]              # T bar, outer tier
COLOR_HUMIDITY_BAND_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Purple"]      # RH band + DP band, outer tier
COLOR_DEW_POINT_ALLOWABLE = COLOR_ROOM_RH                                    # DP bar, outer tier == RH bar's

ALPHA_RECOMMENDED_BAND = 0.35   # every band now (hue, not alpha, marks the tier)

# One colour per representative season-day (winter/spring/summer/fall),
# shared across plot_overview and any other multi-season figure.
SEASON_COLORS = {"winter": ETH_QUAL_BLUE, "spring": ETH_QUAL_GREEN,
                 "summer": ETH_QUAL_RED, "fall": ETH_QUAL_GOLD}

# One colour per refrigerant, shared across any figure comparing all three
# (e.g. analysis/superheat_subcool_sweep.py).
REFRIGERANT_COLORS = {"Propane": ETH_QUAL_BLUE, "R1234yf": ETH_QUAL_GREEN,
                      "DimethylEther": ETH_QUAL_GOLD}


# Sequential (continuous: contour/heatmap) colormaps -- the ONLY consumer is
# plotting.py's Task-2 COP_inner / Q_AC_kW performance-map contour plots.
# Multi-hue (viridis-style) rather than single-hue: better step
# discriminability on the dense COP/Q_AC contours than a single-hue ramp gives.
# Both maps share the same colour scale so the two figures read consistently.
SEQUENTIAL_CMAP_Q_AC = eth_colormaps.cmaps["multi"]
SEQUENTIAL_CMAP_COP = eth_colormaps.cmaps["multi"]