"""
Task 4 entry point. Run from the repository root:
    python src/main_task4.py
(no PYTHONPATH needed - see main.py)

Pipeline: read Task 3's saved per-hour energy table (results/
task3_energy_by_hour.csv, written by main_task3.py -- run that first if
missing) -> cost each hour's energy at that hour's REAL day-ahead price
(common.data_io.load_dayahead_prices; task4.economics also applies the
compressor fluid->electrical conversion, config.ETA_MOTOR_ELEC) -> print a
comparison table, highlight the Task-3-selected design, and write a
cost-comparison bar chart + CSV. Costs are for the four representative days
(matching Task 3's own "kWh / 4 days" convention), not annualised -- see
task4/economics.py's docstring for why.
"""
import os
import pandas as pd
from common import config, data_io, plotting
from task3 import sweep
from task4 import economics

ENERGY_CSV = os.path.join("results", "task3_energy_by_hour.csv")
COMPARISON_CSV = os.path.join("results", "task3_design_comparison.csv")


def main():
    print("=" * 78)
    print("TASK 4 - electricity cost of the AC + ventilation system")
    print("=" * 78)

    prices = data_io.load_dayahead_prices()
    print("\nReal day-ahead prices used (ENTSO-E, Swiss bidding zone BZN|CH):")
    for season in config.SEASONS:
        p = prices[season]["price_chf_per_kwh"]
        print("  %-7s %s  (%.3f-%.3f CHF/kWh)" % (season, prices[season]["date"], p.min(), p.max()))
    print("\nCompressor motor+drive efficiency: %.0f%% (fluid power -> billed "
          "electrical power)" % (100 * config.ETA_MOTOR_ELEC))

    df_energy = economics.load_energy_by_hour(ENERGY_CSV)
    df_cost = economics.design_economics(df_energy, prices)

    df_compare = pd.read_csv(COMPARISON_CSV)
    if "error" in df_compare:
        df_compare = df_compare[df_compare["error"].isna()]
    refrigerant_best, bore_best = sweep.select_best(df_compare)

    df_cost = df_cost.sort_values("cost_total_CHF").reset_index(drop=True)
    hdr = ("refrigerant   bore | E_AC   E_vent  E_tot [kWh/4d] | cost_AC  "
           "cost_vent  cost_tot [CHF/4d]")
    print("\n" + hdr); print("-" * len(hdr))
    for _, r in df_cost.iterrows():
        flag = "  *" if (r["refrigerant"] == refrigerant_best and r["bore_mm"] == bore_best) else ""
        print("%-13s %4.0fmm | %6.1f %7.1f %7.1f       | %7.2f %8.2f %8.2f%s"
              % (r["refrigerant"], r["bore_mm"], r["E_ac_kWh"], r["E_vent_kWh"],
                 r["E_total_kWh"], r["cost_ac_CHF"], r["cost_vent_CHF"],
                 r["cost_total_CHF"], flag))
    print("\n(* = design selected in Task 3; costs are for the 4 representative days, not annualised)")

    sel = df_cost[(df_cost["refrigerant"] == refrigerant_best) & (df_cost["bore_mm"] == bore_best)].iloc[0]
    print("\nSelected design (%s, %.0f mm): CHF %.2f over the 4 representative days "
          "(AC CHF %.2f, ventilation CHF %.2f)"
          % (refrigerant_best, bore_best, sel["cost_total_CHF"],
             sel["cost_ac_CHF"], sel["cost_vent_CHF"]))

    os.makedirs("figures", exist_ok=True)
    fig_path = os.path.join("figures", "task4_cost_comparison.png")
    dates = {s: prices[s]["date"] for s in config.SEASONS}
    plotting.plot_cost_comparison(df_cost, fig_path, best=(refrigerant_best, bore_best), dates=dates)
    print("Figure written to %s" % fig_path)

    price_fig_path = os.path.join("figures", "task4_dayahead_prices.png")
    plotting.plot_dayahead_prices(prices, price_fig_path)
    print("Figure written to %s" % price_fig_path)

    os.makedirs("results", exist_ok=True)
    out_csv = os.path.join("results", "task4_cost_comparison.csv")
    df_cost.to_csv(out_csv, index=False)
    print("Comparison table written to %s" % out_csv)
    return df_cost


if __name__ == "__main__":
    main()
