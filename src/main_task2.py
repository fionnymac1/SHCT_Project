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

    return maps


if __name__ == "__main__":
    main()
