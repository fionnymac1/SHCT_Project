ROOM_LENGTH_M = 10.0
ROOM_WIDTH_M = 6.0
ROOM_HEIGHT_M = 3.0
ROOM_VOLUME_M3 = ROOM_LENGTH_M * ROOM_WIDTH_M * ROOM_HEIGHT_M

FLOW_RATE_ACH = 9.0  # Air Changes per Hour
SAFETY_MARGIN = 1.15  # 15% extra capacity for safety

TARGET_TEMP_C = 15.0
INITIAL_TEMP_C = 15.0
RELATIVE_HUMIDITY = 0.60

TEMP_UPPER_THRESHOLD_C = 16.0
TEMP_LOWER_THRESHOLD_C = 14.0

TIME_STEP_MIN = 5.0
MIN_AC_RUN_TIME_MIN = 5.0
MIN_AC_OFF_TIME_MIN = 10.0

MIN_PRESSURE_RATIO = 2.0
COMPRESSOR_BORES_MM = [30.0, 40.0, 50.0]
REFRIGERANTS = ["Propane", "R1234yf", "DimethylEther"]

FILE_AMBIENT_FALL = "data/ambient_temperature_fall.txt"
FILE_AMBIENT_WINTER = "data/ambient_temperature_winter.txt"
FILE_AMBIENT_SUMMER = "data/ambient_temperature_summer.txt"
FILE_AMBIENT_SPRING = "data/ambient_temperature_spring.txt"
FILE_SERVER_HEAT = "data/server_heating_power.txt"