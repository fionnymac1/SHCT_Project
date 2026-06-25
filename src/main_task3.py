"""
Task 3 entry point. Run from the repository root:
    python src/main_task3.py
(no PYTHONPATH needed - see main.py)

Pipeline: for every compressor bore x refrigerant combination, load the
precomputed Task-2 (T_room, T_amb) performance map (results/*.csv) and run
Task 1's on/off-controlled room simulation over all four representative days
-> aggregate energy demand, AC start/stop cycles, operating times and room
air condition (temperature, humidity) per combination -> rank and select the
most suitable design -> visualize its operation and write a comparison table.

Requires results/*.csv to exist for every (refrigerant, bore) in
config.REFRIGERANTS x config.COMPRESSOR_BORES_MM - run main_task2.py first.

Quick single-combo/single-day check (skips the full sweep, for fast
iteration while developing): e.g.
    python src/main_task3.py --refrigerant Propane --bore 30 --season summer
"""
import argparse
import os
from common import config, plotting
from task3 import sweep


def main_single(refrigerant, bore_mm, season):
    print("Single run: %s, %.0f mm, %s day" % (refrigerant, bore_mm, season))
    r, metrics = sweep.run_single_day(refrigerant, bore_mm, season)
    print("T rec %5.1f%%  T allow %5.1f%%  Tmin %4.1f  Tmax %4.1f  "
          "RH rec %5.1f%%  RH allow %5.1f%%  RHmin %3.0f%%  RHmax %3.0f%%  "
          "AC starts %d  AC-min %.0f  E_tot %.2f kWh"
          % (100 * metrics["frac_T_recommended"], 100 * metrics["frac_T_allowable"],
             metrics["T_min"], metrics["T_max"],
             100 * metrics["frac_phi_recommended"], 100 * metrics["frac_phi_allowable"],
             100 * metrics["phi_min"], 100 * metrics["phi_max"],
             metrics["ac_starts_total"], metrics["ac_min_total"],
             metrics["E_total_kWh"]))
    path = sweep.visualize_single_day(r, refrigerant, bore_mm)
    print("Figure written to %s" % path)
    return r, metrics


def main():
    print("=" * 78)
    print("TASK 3 - simulate & select compressor bore x refrigerant")
    print("=" * 78)
    results_by_design, df_compare = sweep.run_all_designs()
    df_ranked = sweep.rank(df_compare)

    failed = df_compare[df_compare["error"].notna()]
    if not failed.empty:
        print("\n%d combo(s) FAILED to simulate (excluded from ranking):" % len(failed))
        for _, r in failed.iterrows():
            print("  %-14s %4.0f mm : %s" % (r["refrigerant"], r["bore_mm"], r["error"]))

    os.makedirs("results", exist_ok=True)
    out_csv = os.path.join("results", "task3_design_comparison.csv")
    df_ranked.to_csv(out_csv, index=False)

    hdr = ("rank refrigerant   bore | T rec T allow  Tmin Tmax | RH rec RH allow "
           "RHmin RHmax | AC starts AC-min | E_tot kWh")
    print("\n" + hdr); print("-" * len(hdr))
    for _, r in df_ranked.iterrows():
        print("%4d %-13s %4.0fmm | %5.1f%% %7.1f%% %4.1f %4.1f | %6.1f%% %8.1f%% "
              "%4.0f%% %4.0f%% | %9d %6.0f | %9.2f"
              % (r["rank"], r["refrigerant"], r["bore_mm"],
                 100 * r["frac_T_recommended"], 100 * r["frac_T_allowable"],
                 r["T_min"], r["T_max"],
                 100 * r["frac_phi_recommended"], 100 * r["frac_phi_allowable"],
                 100 * r["phi_min"], 100 * r["phi_max"],
                 r["ac_starts_total"], r["ac_min_total"], r["E_total_kWh"]))
    print("\nComparison table written to %s" % out_csv)

    refrigerant, bore_mm = sweep.select_best(df_compare)
    print("\nSelected design: %s, %.0f mm bore" % (refrigerant, bore_mm))

    R = results_by_design[(refrigerant, bore_mm)]
    label = "%s, %.0f mm" % (refrigerant, bore_mm)
    os.makedirs("figures", exist_ok=True)
    for s in config.SEASONS:
        plotting.plot_season(R[s], os.path.join("figures", "task3_%s.png" % s), label=label)
    plotting.plot_overview(R, os.path.join("figures", "task3_overview.png"))
    plotting.plot_design_comparison(
        df_compare[df_compare["error"].isna()], os.path.join("figures", "task3_comparison.png"),
        best=(refrigerant, bore_mm))
    print("Figures written to ./figures/ (task3_winter/spring/summer/fall, "
          "task3_overview, task3_comparison)")

    return results_by_design, df_ranked


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refrigerant", choices=config.REFRIGERANTS)
    parser.add_argument("--bore", type=float, choices=config.COMPRESSOR_BORES_MM)
    parser.add_argument("--season", choices=config.SEASONS)
    args = parser.parse_args()

    if args.refrigerant or args.bore or args.season:
        if not (args.refrigerant and args.bore and args.season):
            parser.error("--refrigerant, --bore and --season must be given together "
                         "for a single-combo/single-day run; omit all three to run "
                         "the full sweep.")
        main_single(args.refrigerant, args.bore, args.season)
    else:
        main()
