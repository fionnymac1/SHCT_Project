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
# Two nested envelopes: RECOMMENDED (comfort/target, drives the on/off
# setpoints below) vs ALLOWABLE (hard safety limit, scored in Task 3).
T_RECOMMENDED_LOW_C = 18.0   # [ASSUMPTION] ASHRAE recommended envelope lower
T_RECOMMENDED_HIGH_C = 27.0  # [ASSUMPTION] ASHRAE recommended envelope upper
T_ALLOW_LOW_C = 10.0         # hard lower limit
T_ALLOW_HIGH_C = 35.0        # hard upper limit
T_BAND_LOW_C = T_RECOMMENDED_LOW_C    # aliases used by flow_limits/simulation
T_BAND_HIGH_C = T_RECOMMENDED_HIGH_C

# Humidity is monitored, not controlled (no (de)humidifier). Allowable only --
# dew point carries the recommended target instead (below).
PHI_ALLOW_LOW = 0.08         # hard lower limit
PHI_ALLOW_HIGH = 0.80        # hard upper limit

# Dew point: both bands. [ASSUMPTION] same family of limit as ASHRAE TC9.9's
# data-centre envelopes (condensation risk above, ESD/static risk below).
# Computed from X via room.dew_point_C (Magnus-Tetens).
DP_RECOMMENDED_LOW_C = -9.0
DP_RECOMMENDED_HIGH_C = 15.0
DP_ALLOW_LOW_C = -9.0
DP_ALLOW_HIGH_C = 17.0

# --------------------------------------------- control (1.3) state machine
# Temperature-only on/off with hysteresis, both setpoints inside the band.
# Cycling/deadband adequacy is checked in analysis (see the setpoint-shift sweep,
# main_setpoint_sweep.py): the relay band has a broad, forgiving optimum.
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
# Minimum run/standstill times: given directly by the project description, not
# an assumption -- not open to revision.
MIN_RUN_MIN = 5.0            # minimum run time      = 1 step
MIN_STANDSTILL_MIN = 10.0    # minimum standstill    = 2 steps

# ------------------------------------------------------ flow limits (1.2)
# Acoustic/comfort velocity cap = Beaufort 5 ("fresh breeze"), Lecture #11:
# 8.0-10.7 m/s; use the upper edge as the not-to-exceed cap.
V_MAX_BEAUFORT5_M_S = 10.7
# Supply-opening face area (not given by the slides; ~0.5 m equivalent opening
# assumed). The course's own ventilator sizing (Lecture 10) uses the blower
# curve, not this cap -- Beaufort-5 stays only as the acoustic ceiling.
A_SUPPLY_M2 = 0.20           # [ASSUMPTION][FLAG] refine to make sure vmax <= 0.25
DELTA_T_SUPPLY_GUIDE_K = 10.0

# ----------------------------------------- ventilation DESIGN flow (1.2 / 1.3)
# Single ON/OFF design flow for free cooling. Sized from the room's 1st-order
# response (tau = M_air/(rho*V)) so the worst VENT step (T_ON, coldest ambient)
# can't undershoot the band floor: f <= (T_ON-T_BAND_LOW)/(T_ON-T_amb_min), giving
# V <= 0.168 m3/s. We take 0.15 m3/s (~0.5 K floor margin, well under the
# Beaufort-5 cap). This gentle a flow only carries ~1-4 kW of free cooling, so
# the AC covers the rest in mild weather -- a trade-off worth owning in the report.
#
# One ventilator, two flows (VFD or damper): free cooling needs this LOW flow,
# AC recirc needs a HIGH flow (else T_AC < T_ev + pinch), and they don't overlap.
# Only the low flow is a free constant here -- the high (AC recirc) flow scales
# with compressor capacity (~bore^2), so it's derived per (bore, refrigerant) in
# flow_limits.ac_fan_flow_from_map(), with the acoustic-cap/turndown coupling
# checked in flow_limits.check_ac_fan_feasible().
VENT_FLOW_DESIGN_M3S = 0.15

# AC-fan sizing ceiling: highest room temperature the recirc fan must serve.
# [ASSUMPTION] set to the worst control overshoot (~35 degC, from standstill-lockout
# x slew-rate), not the band top -- this exposes which bores can't be served
# within the acoustic cap/turndown as a Task-3 feasibility result (warns + clamps,
# not a crash) rather than hiding it behind an optimistic sizing point.
T_ROOM_MAX_DESIGN_C = 35.0
# Fan-power model (damper, ~near-full power at low flow, vs a VFD scaling ~flow^3)
# is flagged as an uncertainty in the report rather than decided here -- see the
# "Flow actuation and fan power" item.

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
#   must resolve; here it is fixed as a defensible stand-in. Whether a
#   per-point optimisation is needed at all is checked in analysis/cop_optimum.py:
#   the constant-approach choice already matches the SLSQP optimum closely.
DT_APPROACH_EVAP_K = 12.0    # -> T_ev = T_room - 12  (3 degC at 15 degC room)
DT_APPROACH_COND_K = 10.0    # [ASSUMPTION] realistic air-cooled approach (field
                             # ~7-12 K; a water-sink approach would be much tighter)
DT_APPROACH_AIR_K = 3.0      # T_AC = T_ev + 3   (answer to setup question 3)
DELTA_T_SUPERHEAT_K = 5.0    # [ASSUMPTION] realistic suction superheat
DELTA_T_SUBCOOL_K = 5.0      # liquid leaves at T_co-5 = T_amb+5 (physical 5 K
                             # condenser cold-end pinch). COP rises monotonically
                             # with subcool to the sink bound (superheat_subcool_
                             # sweep), so this fixed 5 K is conservative, not the
                             # optimum. Affects q_evap/COP only, not m_dot/eta.
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
COMPRESSOR_N_CYL = 2         # confirmed via course Q&A: the task sheet's
                             # "4-cylinder" was a typo; matches recip_comp_corr_SP
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

# [ASSUMPTION] Day-ahead prices are WHOLESALE (what a utility pays on the spot
# market), not the RETAIL tariff an actual commercial customer is billed.
# Swissgrid reports energy as ~46% of a Swiss electricity bill, the rest being
# grid/transport fees and taxes (Swissgrid, "How Electricity Prices Are
# Calculated in Switzerland"; ElCom/upgrid.ch 2026 tariff data) -- i.e. retail
# is roughly 1/0.46 ~= 2.2x the energy-only cost. We approximate this with a
# flat factor of 2 rather than the more precise 2.2, since the comparison is
# already approximate (retail tariffs reflect forward-hedged procurement, not
# the literal day-ahead spot price used here).
RETAIL_MARKUP_FACTOR = 2.0

# [ASSUMPTION] combined compressor motor + drive efficiency, converting the
# compressor model's fluid/shaft power to billed electrical power:
# P_elec = P_fluid / ETA_MOTOR_ELEC. The course's own simplification is 1.0
# (P_elec ~= P_fluid); this owns a realistic value for a small reciprocating
# unit instead. The fan's power is already an electrical stand-in, not divided
# by this.
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
# Both the qualitative (discrete) and sequential (continuous) palettes below
# come from eth_colormaps, used consistently across every plot in plotting.py.
from common import eth_colormaps

ETH_QUAL_BLACK = eth_colormaps.ETH_QUAL["Black"]
ETH_QUAL_BLUE = eth_colormaps.ETH_QUAL["Blue"]
ETH_QUAL_PETROL = eth_colormaps.ETH_QUAL["Petrol"]
ETH_QUAL_GREEN = eth_colormaps.ETH_QUAL["Green"]
ETH_QUAL_GOLD = eth_colormaps.ETH_QUAL["Gold"]
ETH_QUAL_RED = eth_colormaps.ETH_QUAL["Red"]
ETH_QUAL_PURPLE = eth_colormaps.ETH_QUAL["Purple"]
ETH_QUAL_GREY = eth_colormaps.ETH_QUAL["Grey"]

# Semantic roles -- plotting.py reads what a colour MEANS, not a raw hex, so
# the mapping is decided once, here. plot_season uses its own local mapping
# (not these names) for the one-day figures; this block governs every other
# (comparison/overview) figure: green = T/comfort bands, purple = RH/dew
# point, blue = AC, gold = VENT/selected design, black = neutral.
COLOR_ROOM_T = ETH_QUAL_GREEN
COLOR_ROOM_RH = ETH_QUAL_PURPLE
COLOR_DEW_POINT = ETH_QUAL_PURPLE             # band shading is COLOR_HUMIDITY_BAND
COLOR_AC = ETH_QUAL_BLUE             # compressor: duty cycle, energy, starts, cost
COLOR_VENT = ETH_QUAL_GOLD           # ventilation/fan: duty cycle, energy, starts, cost
COLOR_OFF = ETH_QUAL_BLACK           # neutral: OFF duty-cycle segment
COLOR_RECOMMENDED_BAND = ETH_QUAL_GREEN       # T band (allowable = paired shade below)
COLOR_HUMIDITY_BAND = ETH_QUAL_PURPLE         # RH/dew-point band
COLOR_SELECTED_DESIGN = ETH_QUAL_GOLD         # Task-3-selected design highlight outline
COLOR_NEUTRAL = ETH_QUAL_BLACK                # reference lines, contour overlays, etc.

# Recommended/allowable are nested two-tier categories. Every band uses the
# paired companion shade (eth_colormaps.ETH_QUAL_PARTNER) for its outer/
# allowable tier, rather than the same hue at a lower alpha. RH has no
# recommended target, so its one band reuses the purple partner shade too.
COLOR_RECOMMENDED_BAND_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Green"]    # T band, outer tier
COLOR_ROOM_T_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Green"]              # T bar, outer tier
COLOR_HUMIDITY_BAND_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Purple"]      # RH/DP band, outer tier
COLOR_DEW_POINT_ALLOWABLE = eth_colormaps.ETH_QUAL_PARTNER["Purple"]          # DP bar, outer tier

ALPHA_RECOMMENDED_BAND = 0.35   # hue (not alpha) marks the tier; this is shared by all bands

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