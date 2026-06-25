"""
Task 1 entry point. Run from the repository root:
    python src/main.py
(no PYTHONPATH needed - this script lives in src/, which Python adds to
the import path automatically, making common/task1/task2 resolvable)

Pipeline: load data -> Task 1.1/1.2 headline numbers -> build the AC
capacity/COP map (Hint 1) -> simulate the four representative days under the
on/off control state machine (Task 1.3) -> report and plot.
"""
import os
from common import config, data_io, plotting
from task1 import flow_limits, simulation
from task2 import cycle



def main():
    server_raw, _ = data_io.load_raw()

    print("=" * 70)
    print("TASK 1.1 required cooling power  &  1.2 volumetric flow limits")
    print("=" * 70)
    flow_limits.summarise({s: server_raw for s in config.SEASONS})

    print("\nBuilding AC capacity/COP map  (%.0f mm, %s) ..."
          % (config.STANDIN_BORE_MM, config.STANDIN_REFRIGERANT))
    cmap = cycle.build_map()

    print("\n" + "=" * 70)
    print("TASK 1.3 on/off control - four-season simulation")
    print("=" * 70)
    R = simulation.simulate_all(cmap)
    hdr = ("season  | Tmin Tmax  rec  allow | RHmin RHmax  rec  allow | "
           "AC start/min  VENT start/min | E_AC  E_vent")
    print(hdr); print("-" * len(hdr))
    for s in config.SEASONS:
        r = R[s]
        print("%-7s | %4.1f %4.1f %4.0f%% %4.0f%% | %4.0f%% %4.0f%% %4.0f%% %4.0f%% | "
              "%2d /%5.0f   %2d /%5.0f | %5.2f %5.2f kWh"
              % (s, r["T_min"], r["T_max"],
                 100 * r["frac_T_recommended"], 100 * r["frac_T_allowable"],
                 100 * r["phi_min"], 100 * r["phi_max"],
                 100 * r["frac_phi_recommended"], 100 * r["frac_phi_allowable"],
                 r["ac_starts"], r["ac_min"], r["vent_starts"], r["vent_min"],
                 r["E_ac_kWh"], r["E_vent_kWh"]))

    os.makedirs("figures", exist_ok=True)
    for s in config.SEASONS:
        plotting.plot_season(R[s], os.path.join("figures", "task1_%s.png" % s))
    plotting.plot_overview(R, os.path.join("figures", "task1_overview.png"))
    print("\nFigures written to ./figures/")
    return R


if __name__ == "__main__":
    main()
