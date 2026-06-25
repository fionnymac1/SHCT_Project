"""
Task 2 entry point. Run from the repository root:
    python src/main_task2.py
(no PYTHONPATH needed - see main.py)

Pipeline: load the real ambient-temperature data (via data_io, the same
loader Task 1 uses) to bound the sink-temperature grid -> build the AC
cycle's (T_room, T_amb) capacity/COP map (cycle.build_map) for every
compressor bore x refrigerant combination -> save each map via data_io.
"""
from common import config, data_io
from task1 import flow_limits
from task2 import cycle


def main():
    t_room_grid, t_amb_grid = cycle.default_grids()
    t_amb_max = float(t_amb_grid.max())
    print("Ambient grid: %.1f to %.1f degC | room grid: %.1f to %.1f degC"
          % (t_amb_grid.min(), t_amb_max, t_room_grid.min(), t_room_grid.max()))

    print("\n%-14s %6s %12s %12s" % ("refrigerant", "bore", "COP@T_amb_max", "Q_AC@T_amb_max"))
    print("-" * 48)
    maps = {}
    for refrigerant in config.REFRIGERANTS:
        for bore in config.COMPRESSOR_BORES_MM:
            cmap = cycle.build_map(T_room_grid=t_room_grid, T_amb_grid=t_amb_grid,
                                    bore_mm=bore, refrigerant=refrigerant)
            maps[(refrigerant, bore)] = cmap

            df = cycle.map_to_dataframe(cmap)
            path = data_io.save_performance_map(df, refrigerant, bore)

            Q, cop = cycle.lookup(cmap, config.T_INIT_C, t_amb_max)
            print("%-14s %4.0fmm %12.2f %12.2f   -> %s"
                  % (refrigerant, bore, cop, Q, path))

    # ---- Task 1.2 follow-up: one-flow-vs-two-flow ventilation trade-off ----
    # If the SINGLE ventilator ran free cooling at the AC recirc flow (V_vent =
    # V_AC) instead of the gentle design flow, what room-ambient dT would free
    # cooling need to carry the PEAK load? Coverage dT only -- the same flow
    # overshoots the LOW band at any larger dT (see config.VENT_FLOW_DESIGN_M3S).
    server_raw, _ = data_io.load_raw()
    q_peak = flow_limits.required_cooling_power_kw(
        {s: server_raw for s in config.SEASONS})
    gentle_dt = q_peak / (config.AIR_DENSITY_KG_M3 * config.CP_AIR_KJ_KGK
                          * config.VENT_FLOW_DESIGN_M3S)
    print("\nFree-cooling dT to cover the %.2f kW peak if V_vent = V_AC" % q_peak)
    print("  (gentle V_design = %.2f m3/s would need dT = %.0f K):"
          % (config.VENT_FLOW_DESIGN_M3S, gentle_dt))
    print("  %-16s %8s %7s %10s" % ("combo", "Qmax_kW", "V_AC", "dT_free_K"))
    print("  " + "-" * 45)
    for refrigerant in config.REFRIGERANTS:
        for bore in config.COMPRESSOR_BORES_MM:
            q_max, v_ac, dt = flow_limits.freecool_dt_for_ac_flow(
                maps[(refrigerant, bore)], q_peak)
            print("  %-16s %8.1f %7.2f %10.1f"
                  % ("%s %.0fmm" % (refrigerant, bore), q_max, v_ac, dt))

    return maps


if __name__ == "__main__":
    main()
