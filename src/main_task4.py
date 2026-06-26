"""
Task 4 entry point. Run from the repository root:
    python src/main_task4.py
(no PYTHONPATH needed - see main.py)

Pipeline: read Task 3's saved per-season energy table (results/
task3_energy_by_season.csv, written by main_task3.py -- run that first if
missing) -> convert each design's per-season energy to an annual electrical
cost (task4.economics: tariff per config.ELEC_PRICE_CHF_PER_KWH, compressor
fluid->electrical conversion per config.ETA_MOTOR_ELEC) -> print a comparison
table, highlight the Task-3-selected design, and write a cost-comparison
bar chart + CSV.
"""
import os
import pandas as pd
from common import config, plotting
from task3 import sweep
from task4 import economics

ENERGY_CSV = os.path.join("results", "task3_energy_by_season.csv")
COMPARISON_CSV = os.path.join("results", "task3_design_comparison.csv")


def main():
    print("=" * 78)
    print("TASK 4 - electricity cost of the AC + ventilation system")
    print("=" * 78)

    df_energy = economics.load_energy_by_season(ENERGY_CSV)
    df_cost = economics.design_economics(df_energy)

    df_compare = pd.read_csv(COMPARISON_CSV)
    if "error" in df_compare:
        df_compare = df_compare[df_compare["error"].isna()]
    refrigerant_best, bore_best = sweep.select_best(df_compare)

    print("\nTariff (CHF/kWh) by season: %s" % config.ELEC_PRICE_CHF_PER_KWH)
    print("Compressor motor+drive efficiency: %.0f%% (fluid power -> billed "
          "electrical power)" % (100 * config.ETA_MOTOR_ELEC))
    print("Each representative day scaled to %.1f days/year (one season)\n"
          % config.DAYS_PER_REPRESENTATIVE_SEASON)

    df_cost = df_cost.sort_values("cost_total_CHF_year").reset_index(drop=True)
    hdr = ("refrigerant   bore | E_AC/yr  E_vent/yr  E_tot/yr [kWh] | cost_AC  "
           "cost_vent  cost_tot [CHF/yr]")
    print(hdr); print("-" * len(hdr))
    for _, r in df_cost.iterrows():
        flag = "  *" if (r["refrigerant"] == refrigerant_best and r["bore_mm"] == bore_best) else ""
        print("%-13s %4.0fmm | %7.0f %8.0f %8.0f       | %7.0f %8.0f %8.0f%s"
              % (r["refrigerant"], r["bore_mm"], r["E_ac_year_kWh"], r["E_vent_year_kWh"],
                 r["E_total_year_kWh"], r["cost_ac_CHF_year"], r["cost_vent_CHF_year"],
                 r["cost_total_CHF_year"], flag))
    print("\n(* = design selected in Task 3)")

    sel = df_cost[(df_cost["refrigerant"] == refrigerant_best) & (df_cost["bore_mm"] == bore_best)].iloc[0]
    print("\nSelected design (%s, %.0f mm): CHF %.0f / year total "
          "(AC CHF %.0f, ventilation CHF %.0f)"
          % (refrigerant_best, bore_best, sel["cost_total_CHF_year"],
             sel["cost_ac_CHF_year"], sel["cost_vent_CHF_year"]))

    os.makedirs("figures", exist_ok=True)
    fig_path = os.path.join("figures", "task4_cost_comparison.png")
    plotting.plot_cost_comparison(df_cost, fig_path, best=(refrigerant_best, bore_best))
    print("\nFigure written to %s" % fig_path)

    os.makedirs("results", exist_ok=True)
    out_csv = os.path.join("results", "task4_cost_comparison.csv")
    df_cost.to_csv(out_csv, index=False)
    print("Comparison table written to %s" % out_csv)
    return df_cost


if __name__ == "__main__":
    main()
