import config

def cooling_controller(t_room, t_ambient, current_state, time_in_current_state):
    """
    Determines the next state of the cooling system based on sensor data.
    
    States: 'OFF', 'VENTILATION_ON', 'AC_ON'
    """
    # Define Thresholds
    t_upper = config.TEMP_UPPER_THRESHOLD_C  # Turn on cooling when room exceeds this
    t_lower = config.TEMP_LOWER_THRESHOLD_C  # Turn off cooling when room drops below this

    # Define Time Constraints (in minutes)
    min_ac_run_time = config.MIN_AC_RUN_TIME_MIN
    min_ac_off_time = config.MIN_AC_OFF_TIME_MIN

    # 1. Check Mandatory AC Timers First
    if current_state == 'AC_ON' and time_in_current_state < min_ac_run_time:
        return 'AC_ON' # Forced to keep running
        
    if current_state == 'OFF' and time_in_current_state < min_ac_off_time:
        return 'OFF' # Forced to stay off
        
    # 2. Determine Required Cooling Action
    if t_room > t_upper:
        # We need cooling. Check if ambient air is cold enough to use ventilation.
        # Assuming ambient air needs to be at least 2 degrees colder than the target to be effective.
        if t_ambient < (t_lower - 2.0): 
            return 'VENTILATION_ON'
        else:
            return 'AC_ON'
            
    elif t_room < t_lower:
        # Room is cool enough, shut down.
        return 'OFF'
        
    else:
        # Room is in the acceptable range (14-16 degrees). Maintain current state.
        # (Unless it was forced off/on by the timers above, which is already handled).
        if current_state == 'VENTILATION_ON' and t_ambient >= t_lower:
             # Failsafe: if outside gets too warm while venting, switch to AC or OFF
             return 'AC_ON' 
        return current_state