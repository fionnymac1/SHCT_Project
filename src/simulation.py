import config

def determine_system_limits(server_heat_data):
    """
    Task 1: Estimates volumetric flow limits and peak cooling demand.
    """
    # 1. Flow Limit (9 ACH)
    max_flow_limit = (config.ROOM_VOLUME_M3 * config.FLOW_RATE_ACH) / 3600.0 
    
    # 2. Peak Cooling Demand
    peak_cooling_demand = max(server_heat_data)
    
    return max_flow_limit, peak_cooling_demand