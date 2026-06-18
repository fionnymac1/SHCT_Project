import config
import numpy as np
import pandas as pd
import Fluid_CP as FCP
from compressor_model import recip_comp_corr_SP

def determine_system_limits(server_heat_data):
    """
    Task 1: Estimates volumetric flow limits and peak cooling demand.
    """
    # 1. Flow Limit (9 ACH)
    max_flow_limit = (config.ROOM_VOLUME_M3 * config.FLOW_RATE_ACH) / 3600.0 
    
    # 2. Peak Cooling Demand
    peak_cooling_demand = max(server_heat_data) * config.SAFETY_MARGIN  # kW, with safety margin
    
    return max_flow_limit, peak_cooling_demand

def calculate_ac_performance(T_amb, T_room, refrigerant, D_bore):
    """
    Calculates the AC cooling capacity and COP_inner for a specific ambient temperature.
    
    Parameters:
    - T_amb (float): Ambient outside temperature in °C.
    - T_room (float): Room temperature in °C.
    - refrigerant (str): Refrigerant name (e.g., "Propane", "R1234yf", "Dimethyl ether").
    - D_bore (float): Compressor cylinder diameter in mm (30, 40, or 50).
    
    Returns:
    - tuple: (Q_AC_kW, COP_inner, P_elec_kW)
    """
    # Design Assumptions (Standard Engineering Baseline)
    dT_approach = 5.0    # K (Approach temperature for heat exchangers)
    dT_sh = 5.0          # K (Superheat)
    dT_sc = 0.0          # K (Subcooling - assumed zero unless specified)
    
    # 1. Establish Ideal Boundary Temperatures
    T_ev = T_room - dT_approach
    T_co_ideal = T_amb + dT_approach
    
    # 2. Get Pressures to check the operating envelope
    state_ev = FCP.state(["T", "x"], [T_ev, 1.0], refrigerant, Eh="CBar")
    P_ev = state_ev["p"]
    
    state_co_ideal = FCP.state(["T", "x"], [T_co_ideal, 0.0], refrigerant, Eh="CBar")
    P_co_ideal = state_co_ideal["p"]
    
    # 3. Enforce Minimum Pressure Ratio of 2.0
    if (P_co_ideal / P_ev) < 2.0:
        P_co_real = P_ev * 2.0
        # Recalculate condensing temperature at this forced higher pressure
        state_co_real = FCP.state(["p", "x"], [P_co_real, 0.0], refrigerant, Eh="CBar")
        T_co = state_co_real["T"]
    else:
        P_co_real = P_co_ideal
        T_co = T_co_ideal
        
    # 4. Call the empirical compressor model
    # param format required: (T_ev, T_co, DeltaT_sh, DeltaT_sc, D)
    param = (T_ev, T_co, dT_sh, dT_sc, D_bore)
    eta_is, m_dot = recip_comp_corr_SP(param, refrigerant, transcrit=False)
    
    # 5. Extract specific enthalpies for power calculations
    # State 1: Compressor Inlet (Evaporating pressure + Superheat)
    T1 = T_ev + dT_sh
    state1 = FCP.state(["T", "p"], [T1, P_ev], refrigerant, Eh="CBar")
    h1 = state1["h"]  # kJ/kg
    s1 = state1["s"]
    
    # State 2s: Isentropic Compressor Outlet
    state2s = FCP.state(["p", "s"], [P_co_real, s1], refrigerant, Eh="CBar")
    h2s = state2s["h"] # kJ/kg
    
    # State 3: Condenser Outlet (Liquid)
    # Assumes expansion is isenthalpic, so h3 = h4 (Evaporator inlet)
    # With dT_sc=0, T3 == T_co lands exactly on the saturation dome, where (T,p)
    # no longer uniquely defines a state -> query via quality (x=0) instead.
    if dT_sc <= 0:
        state3 = FCP.state(["p", "x"], [P_co_real, 0.0], refrigerant, Eh="CBar")
    else:
        T3 = T_co - dT_sc
        state3 = FCP.state(["T", "p"], [T3, P_co_real], refrigerant, Eh="CBar")
    h3 = state3["h"] # kJ/kg
    
    # 6. Calculate System Performance
    # Specific work and heat (kJ/kg)
    w_is = h2s - h1
    w_real = w_is / eta_is
    q_evap = h1 - h3
    
    # Total Power (Mass Flow [kg/s] * Specific Energy [kJ/kg] = kW)
    Q_AC_kW = m_dot * q_evap
    P_elec_kW = m_dot * w_real
    COP_inner = Q_AC_kW / P_elec_kW
    
    return Q_AC_kW, COP_inner, P_elec_kW


def generate_performance_map(refrigerant, D_bore):
    ambient_temps = np.arange(-15, 41, 1)
    room_temps    = np.arange(10, 22, 1)        # source axis, matching the slide
    results = []
    for T_amb in ambient_temps:
        for T_room in room_temps:
            Q, cop, P = calculate_ac_performance(T_amb, T_room, refrigerant, D_bore)
            results.append({"T_amb": T_amb, "T_room": T_room,
                            "Q_AC_kW": Q, "COP_inner": cop, "P_elec_kW": P})
    df_map = pd.DataFrame(results)
    df_map.to_csv(f"ac_map_{refrigerant}_{D_bore:.0f}mm.csv", index=False)
    return df_map