"""
Central configuration for the server-room cooling project (Task 1).
ETH SHCT SS2026.

UNIT CONVENTION
---------------
The course wrappers (Fluid_CP, Fluid_CP_moist_air, Eh="CBar") and the provided
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
# rho_dry ~ 1.197 kg/m3 at 15 degC / 60 % RH  ->  m_air ~ 216 kg  (brief).
AIR_DENSITY_KG_M3 = 1.19
M_AIR_KG = AIR_DENSITY_KG_M3 * ROOM_VOLUME_M3                          # ~216 kg
CP_AIR_KJ_KGK = 1.006        # dry-air cp, for the sensible V_min estimate only

# ----------------------------------------------------------- initial state
T_INIT_C = 15.0
PHI_INIT = 0.60
P_BAR = 1.0

# ----------------------------------------------- acceptable room-air bands
# Temperature: 15 degC is the ALLOWABLE FLOOR (ASHRAE TC9.9 Class A1 lower +
# task target), NOT a centre. The band sits on/above 15 degC and is asymmetric.
T_BAND_LOW_C = 15.0          # [ASSUMPTION] never overcool below this
T_BAND_HIGH_C = 18.0         # [ASSUMPTION] upper acceptable limit
# Humidity is MONITORED, not controlled (no (de)humidifier actuator). The
# binding risk is the LOWER bound: AC condensation dries the room.
#TODO: Humidity monitored, not controlled. Analyze in the results
PHI_ALLOW_LOW = 0.14         # ASHRAE A1 allowable lower
PHI_ALLOW_HIGH = 0.80        # ASHRAE A1 allowable upper (start at 60 % is legal)

# --------------------------------------------- control (1.3) state machine
# Temperature-only on/off with hysteresis, both setpoints inside the band.
# TODO: check the delta of the bang bang controller is sufficient to prevent excessive cycling
T_OFF_C = 15.5               # cooling switches OFF at/below this
T_ON_C = 17.5                # cooling switches ON  at/above this
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
#TODO: corroborate with ex.10 to see if it is sufficient
A_SUPPLY_M2 = 0.20           # [ASSUMPTION][FLAG] refine against a real grille
# Slide 35 rule of thumb: a supply dT of ~10 K is needed to keep velocities
# acceptable -> this couples the flow cap to the evaporator temperature.
DELTA_T_SUPPLY_GUIDE_K = 10.0

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
DT_APPROACH_EVAP_K = 12.0    # -> T_ev = T_room - 12  (3 degC at 15 degC room)
DT_APPROACH_COND_K = 5.0     # [ASSUMPTION]
DT_APPROACH_AIR_K = 3.0      # T_AC = T_ev + 3   (answer to setup question 3)
DELTA_T_SUPERHEAT_K = 5.0    # [ASSUMPTION] realistic suction superheat
DELTA_T_SUBCOOL_K = 0.0      # note: IGNORED by the compressor fn; affects
                             # refrigerating effect / COP only, not m_dot or eta
MIN_PRESSURE_RATIO = 2.0     # compressor envelope; binds at low ambient

# Stand-in (bore, refrigerant) for the Task-1 demonstration run.
# The full sweep over BORES x REFRIGERANTS is Task 3.
STANDIN_BORE_MM = 40.0
STANDIN_REFRIGERANT = "Propane"
ROOM_VOLUME_M3 = ROOM_LENGTH_M * ROOM_WIDTH_M * ROOM_HEIGHT_M


# ----------------------------------------------------------- ASHRAE limits for ventilation
FLOW_RATE_ACH = 9.0  # Air Changes per Hour
SAFETY_MARGIN = 1.15  # 15% extra capacity for safety

MIN_PRESSURE_RATIO = 2.0
COMPRESSOR_BORES_MM = [30.0, 40.0, 50.0]
COMPRESSOR_N_CYL = 4         # [FLAG] provided fn is written for 2 cylinders;
                             # cylinder scaling unresolved -> see RICM60S sheet.
REFRIGERANTS = ["Propane", "R1234yf", "DimethylEther"]   # exact CoolProp names

# Part-load degradation (Hint 2): COP_res = COP_inner * PLR / (0.9*PLR + 0.1)
PART_LOAD_A = 0.9
PART_LOAD_B = 0.1

# ---------------------------------------------------------- ventilation
VENT_AMBIENT_PHI = 0.60      # ambient air is 60 % RH (brief)

# ---------------------------------------------------------- input data
SEASONS = ["winter", "spring", "summer", "fall"]
FILE_AMBIENT = {s: "data/ambient_temperature_{}.txt".format(s) for s in SEASONS}
FILE_SERVER_HEAT = "data/server_heating_power.txt"
# Each input file holds 48 values per representative season-day.
# [ASSUMPTION][FLAG] 48 pts over 24 h => 30-min sampling; day treated periodic.
DATA_POINTS_PER_DAY = 48
DATA_RESOLUTION_MIN = 30.0
DAY_MIN = 24.0 * 60.0
