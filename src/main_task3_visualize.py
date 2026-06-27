"""
Task 3 visualizer - regenerate the design-comparison figures from the
already-computed results/task3_design_comparison.csv, without re-running the
Task 3 simulation sweep. Run from the repository root:
    python src/main_task3_visualize.py
(no PYTHONPATH needed - see main.py)

Useful after tweaking plotting.py: main_task3.py's full sweep (9 combos x 4
seasons of room simulation) takes a while; this just re-reads the CSV it
already wrote and re-draws the bar charts.
"""
import os
import pandas as pd
from common import config, plotting

CSV_PATH = os.path.join("results", "task3_design_comparison.csv")

# Match main_plots.py's DPI override exactly (it sets this same constant
# before plotting) so this script can't drift from it -- config.py's own
# FIGURE_DPI default currently happens to match, but that's a coincidence
# this script shouldn't rely on.
config.FIGURE_DPI = 400


def main():
    df = pd.read_csv(CSV_PATH)
    df_ok = df[df["error"].isna()] if "error" in df else df

    best = df_ok.sort_values("rank").iloc[0]
    refrigerant, bore_mm = best["refrigerant"], float(best["bore_mm"])
    print("Best design from %s: %s, %.0f mm (rank %d)"
          % (CSV_PATH, refrigerant, bore_mm, best["rank"]))

    os.makedirs("figures", exist_ok=True)
    plotting.plot_design_comparison(
        df_ok, os.path.join("figures", "task3_comparison.png"),
        best=(refrigerant, bore_mm))
    plotting.plot_design_comparison_detailed(
        df_ok, os.path.join("figures", "task3_comparison_detail.png"),
        best=(refrigerant, bore_mm))
    print("Figures written to figures/task3_comparison.png and "
          "figures/task3_comparison_detail.png")


if __name__ == "__main__":
    main()
