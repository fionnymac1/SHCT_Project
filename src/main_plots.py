"""
Unified plot generator. Run from the repository root:
    python src/main_plots.py
(no PYTHONPATH needed - see main.py)

Regenerates ANY of the project's report figures from already-computed
results (results/*.csv, data/*) WITHOUT re-running any simulation -- toggle
the PLOT_* flags below, set DPI/SAVE_FIGURES, then run. Each flag's data
dependency (run that script first if its CSV is missing):

    PLOT_TASK1_SEASONS/OVERVIEW    results/task1_<season>.csv          <- main.py
    PLOT_TASK2_HEATMAPS            results/ac_map_*.csv                <- main_task2.py
    PLOT_TASK2_PINCH_OPTIMALITY    figures/task2_pinch_grid_cache.npz   <- analysis/cop_optimum.py
    PLOT_TASK3_SEASONS/OVERVIEW    results/task3_<season>.csv          <- main_task3.py
    PLOT_TASK3_COMPARISON(_DETAIL) results/task3_design_comparison.csv <- main_task3.py
    PLOT_TASK4_COST                results/task4_cost_comparison.csv  <- main_task4.py
    PLOT_TASK4_PRICES              data/GUI_ENERGY_PRICES_*.csv (read directly, no sim)

A missing CSV SKIPS just that group (prints which main_*.py to run first)
instead of aborting the rest. DPI is applied to every figure uniformly via
config.FIGURE_DPI, which plotting.py's savefig calls all read from.
"""
import os
import sys
import pandas as pd
from common import config, data_io, plotting
from task3 import sweep

# analysis/ is a sibling of src/, not a package under it -- add the repo root
# so "from analysis import cop_optimum" resolves regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ----------------------------------------------------- which plots to generate
PLOT_TASK1_SEASONS           = False   # figures/task1_<season>.png            (4 figures)
PLOT_TASK1_OVERVIEW          = False  # figures/task1_overview.png
PLOT_TASK2_HEATMAPS          = False   # figures/task2_COP_inner_grid.png, task2_Q_AC_kW_grid.png
PLOT_TASK2_PINCH_OPTIMALITY  = False  # figures/task2_pinch_optimality.png (re-rendered from the cached grid, no SLSQP re-run)
PLOT_TASK3_SEASONS           = True  # figures/task3_<season>.png   (selected design, 4 figures)
PLOT_TASK3_OVERVIEW          = True   # figures/task3_overview.png   (selected design)
PLOT_TASK3_COMPARISON        = True # figures/task3_comparison.png
PLOT_TASK3_COMPARISON_DETAIL = True  # figures/task3_comparison_detail.png
PLOT_TASK4_COST              = False  # figures/task4_cost_comparison.png
PLOT_TASK4_PRICES            = False  # figures/task4_dayahead_prices.png

SAVE_FIGURES = True   # False -> report what WOULD be (re)generated, write nothing
DPI          = 400    # resolution for every figure below (plotting.py reads config.FIGURE_DPI)

FIGURES_DIR = "figures"
RESULTS_DIR = "results"
config.FIGURE_DPI = DPI


def _skip(name, requires, exc):
    print("  SKIPPED %-28s missing %s (%s)" % (name, requires, exc))


def _selected_design(df_compare):
    """(refrigerant, bore_mm) of the Task-3-selected design."""
    df_ok = df_compare[df_compare["error"].isna()] if "error" in df_compare else df_compare
    return sweep.select_best(df_ok)


def _write(name, fig_or_none, path):
    if SAVE_FIGURES:
        print("  wrote %s" % path)
    else:
        print("  would write %s" % path)


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    print("=" * 78)
    print("UNIFIED PLOT GENERATOR  (CSV-driven, no re-simulation; DPI=%d, SAVE_FIGURES=%s)"
          % (DPI, SAVE_FIGURES))
    print("=" * 78)

    # ---------------------------------------------------------------- Task 1
    if PLOT_TASK1_SEASONS or PLOT_TASK1_OVERVIEW:
        try:
            R = {s: data_io.load_season_result(os.path.join(RESULTS_DIR, "task1_%s.csv" % s))
                 for s in config.SEASONS}
            if PLOT_TASK1_SEASONS:
                for s in config.SEASONS:
                    path = os.path.join(FIGURES_DIR, "task1_%s.png" % s)
                    if SAVE_FIGURES:
                        plotting.plot_season(R[s], path)
                    _write("task1_%s" % s, None, path)
            if PLOT_TASK1_OVERVIEW:
                path = os.path.join(FIGURES_DIR, "task1_overview.png")
                if SAVE_FIGURES:
                    plotting.plot_overview(R, path)
                _write("task1_overview", None, path)
        except FileNotFoundError as exc:
            _skip("PLOT_TASK1_SEASONS/OVERVIEW", "results/task1_<season>.csv", exc)

    # ---------------------------------------------------------------- Task 2
    if PLOT_TASK2_HEATMAPS:
        try:
            maps = data_io.load_all_performance_maps()
            for value in ("COP_inner", "Q_AC_kW"):
                path = os.path.join(FIGURES_DIR, "task2_%s_grid.png" % value)
                if SAVE_FIGURES:
                    fig = plotting.visualize_all_maps(maps, value=value, save=False)
                    fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
                _write("task2_%s_grid" % value, None, path)
        except FileNotFoundError as exc:
            _skip("PLOT_TASK2_HEATMAPS", "results/ac_map_*.csv", exc)

    if PLOT_TASK2_PINCH_OPTIMALITY:
        try:
            from analysis.cop_optimum import load_pinch_grid, plot_pinch_check
            grid = load_pinch_grid(os.path.join(FIGURES_DIR, "task2_pinch_grid_cache.npz"))
            path = os.path.join(FIGURES_DIR, "task2_pinch_optimality.png")
            if SAVE_FIGURES:
                plot_pinch_check(grid, path)
            _write("task2_pinch_optimality", None, path)
        except FileNotFoundError as exc:
            _skip("PLOT_TASK2_PINCH_OPTIMALITY",
                  "figures/task2_pinch_grid_cache.npz (run analysis/cop_optimum.py first)", exc)

    # ---------------------------------------------------------------- Task 3
    df_compare = None
    if any([PLOT_TASK3_SEASONS, PLOT_TASK3_OVERVIEW, PLOT_TASK3_COMPARISON,
            PLOT_TASK3_COMPARISON_DETAIL, PLOT_TASK4_COST]):
        try:
            df_compare = pd.read_csv(os.path.join(RESULTS_DIR, "task3_design_comparison.csv"))
        except FileNotFoundError as exc:
            _skip("PLOT_TASK3_*/PLOT_TASK4_COST", "results/task3_design_comparison.csv", exc)

    if df_compare is not None and (PLOT_TASK3_SEASONS or PLOT_TASK3_OVERVIEW):
        try:
            R3 = {s: data_io.load_season_result(os.path.join(RESULTS_DIR, "task3_%s.csv" % s))
                 for s in config.SEASONS}
            refrigerant, bore_mm = _selected_design(df_compare)
            label = "%s, %.0f mm" % (refrigerant, bore_mm)
            if PLOT_TASK3_SEASONS:
                for s in config.SEASONS:
                    path = os.path.join(FIGURES_DIR, "task3_%s.png" % s)
                    if SAVE_FIGURES:
                        plotting.plot_season(R3[s], path, label=label)
                    _write("task3_%s" % s, None, path)
            if PLOT_TASK3_OVERVIEW:
                path = os.path.join(FIGURES_DIR, "task3_overview.png")
                if SAVE_FIGURES:
                    plotting.plot_overview(R3, path, label=label)
                _write("task3_overview", None, path)
        except (FileNotFoundError, KeyError) as exc:
            _skip("PLOT_TASK3_SEASONS/OVERVIEW", "results/task3_<season>.csv "
                  "(or a stale task3_design_comparison.csv schema)", exc)

    if df_compare is not None and (PLOT_TASK3_COMPARISON or PLOT_TASK3_COMPARISON_DETAIL):
        try:
            df_ok = df_compare[df_compare["error"].isna()] if "error" in df_compare else df_compare
            best = _selected_design(df_compare)
            if PLOT_TASK3_COMPARISON:
                path = os.path.join(FIGURES_DIR, "task3_comparison.png")
                if SAVE_FIGURES:
                    plotting.plot_design_comparison(df_ok, path, best=best)
                _write("task3_comparison", None, path)
            if PLOT_TASK3_COMPARISON_DETAIL:
                path = os.path.join(FIGURES_DIR, "task3_comparison_detail.png")
                if SAVE_FIGURES:
                    plotting.plot_design_comparison_detailed(df_ok, path, best=best)
                _write("task3_comparison_detail", None, path)
        except KeyError as exc:
            _skip("PLOT_TASK3_COMPARISON(_DETAIL)", "a column in task3_design_comparison.csv "
                  "(stale schema -- re-run main_task3.py)", exc)

    # ---------------------------------------------------------------- Task 4
    if PLOT_TASK4_COST or PLOT_TASK4_PRICES:
        prices = data_io.load_dayahead_prices()   # real input data, not a sim result
        if PLOT_TASK4_COST:
            if df_compare is None:
                _skip("PLOT_TASK4_COST", "results/task3_design_comparison.csv",
                      "needed to highlight the selected design")
            else:
                try:
                    df_cost = pd.read_csv(os.path.join(RESULTS_DIR, "task4_cost_comparison.csv"))
                    best = _selected_design(df_compare)
                    dates = {s: prices[s]["date"] for s in config.SEASONS}
                    path = os.path.join(FIGURES_DIR, "task4_cost_comparison.png")
                    if SAVE_FIGURES:
                        plotting.plot_cost_comparison(df_cost, path, best=best, dates=dates)
                    _write("task4_cost_comparison", None, path)
                except (FileNotFoundError, KeyError) as exc:
                    _skip("PLOT_TASK4_COST", "results/task4_cost_comparison.csv "
                          "(or a stale task3_design_comparison.csv schema)", exc)
        if PLOT_TASK4_PRICES:
            path = os.path.join(FIGURES_DIR, "task4_dayahead_prices.png")
            if SAVE_FIGURES:
                plotting.plot_dayahead_prices(prices, path)
            _write("task4_dayahead_prices", None, path)


if __name__ == "__main__":
    main()
