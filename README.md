# SHCT Server-Room Cooling Project

Design and simulation of a sustainable cooling system for a server room
(Sustainable Heating and Cooling Technologies, SS2026). The room is modelled
as a 0-D moist-air control volume, cooled by free-air ventilation and/or a
subcritical vapour-compression cycle, under on/off control, over four
representative season-days.

## Setup

Requires Python 3.11 (the project was developed and tested against it).

```bash
pip install -r requirements.txt
```

`requirements.txt` pins exact versions, including `CoolProp` (the
course-provided property backend used everywhere via `common/Fluid_CP*.py`)
and `colorspacious` (only needed for the ETH colour palette in
`common/eth_colormaps.py`).

All commands below are run from the **repository root** (not `src/`) —
every entry-point script lives in `src/` but resolves its own imports, so no
`PYTHONPATH` setup is needed.

## Running the pipeline

The tasks build on each other in order; later steps read CSVs written by
earlier ones (under `results/`).

| Step | Command | What it does |
|---|---|---|
| Task 1 | `python src/main.py` | Required cooling power / flow limits, builds the stand-in (Propane, 30 mm) capacity map, runs the on/off-controlled room simulation over all four days, writes `results/task1_<season>.csv` and `figures/task1_*.png`. |
| Task 2 | `python src/main_task2.py` | Builds the AC capacity/COP performance map for every (refrigerant, bore) combination, writes `results/ac_map_*.csv`. |
| Task 2 (viz) | `python src/main_task2_viz.py` | Renders the `COP_inner`/`Q_AC_kW` contour-grid figures from the maps `main_task2.py` wrote. |
| Task 3 | `python src/main_task3.py` | Runs the full sweep: simulates all 9 (refrigerant, bore) combinations over all 4 days, ranks them, and writes `results/task3_design_comparison.csv`, `results/task3_<season>.csv` (selected design), `results/task3_energy_by_hour.csv` (Task 4 input), and the comparison figures. **This is the slow step** (full sweep takes tens of minutes; CoolProp calls dominate). For a fast single-combo/single-day check while iterating, use e.g. `python src/main_task3.py --refrigerant Propane --bore 30 --season summer`. |
| Task 3 (viz) | `python src/main_task3_visualize.py` | Re-draws the Task-3 comparison figures from the already-written `task3_design_comparison.csv`, without re-running the simulation sweep. Use this after tweaking `plotting.py`. |
| Task 4 | `python src/main_task4.py` | Costs the selected design's per-hour energy (from Task 3) against real day-ahead electricity prices (`data/GUI_ENERGY_PRICES_*.csv`), writes `results/task4_cost_comparison.csv` and a cost-comparison figure. |
| All figures | `python src/main_plots.py` | Regenerates every figure in `figures/` from whatever results CSVs already exist, without re-running any simulation. Safe to run any time after the above; skips (and reports) any figure whose input CSV is missing. |

Optional, exploratory (not required for the main results):
- `python analysis/sensitivity.py` — one-at-a-time sweep of design/model
  parameters, explaining the room-temperature overshoot.
- `python analysis/superheat_subcool_sweep.py` — justifies the fixed
  superheat/subcooling used in the Task-2 map.
- `python analysis/cop_optimum.py` — runs the true SLSQP inner-cycle optimizer
  over a $(T_{room}, T_{amb})$ grid and compares it against the constant-approach
  map (Task 2), justifying why the map doesn't need a per-point solver. **Slow**
  (several minutes; add `--all-combos` for ~5-7 min more to check every
  refrigerant/bore). Writes `figures/task2_pinch_optimality.png` and caches the
  grid to `figures/task2_pinch_grid_cache.npz`; re-render the figure later
  without re-running the optimizer via `python analysis/cop_optimum.py
  --from-cache figures/task2_pinch_grid_cache.npz`, or via `main_plots.py`'s
  `PLOT_TASK2_PINCH_OPTIMALITY` flag.
- `python src/main_setpoint_sweep.py` — searches the on/off setpoint
  placement (constant shift vs. ambient-scheduled) rather than guessing it.

## Project layout

```
src/
  common/      shared config, CoolProp/psychrometrics wrappers, plotting, colour scheme
  task1/       room ODE model, on/off control, flow-limit sizing
  task2/       vapour-compression cycle, performance-map builder
  task3/       multi-day sweep, ranking, design selection
  task4/       electricity-cost evaluation against real day-ahead prices
  main_*.py    entry points (see table above)
analysis/      standalone diagnostic/sensitivity/optimizer scripts (not part of the main pipeline)
data/          provided input data (server load, ambient temperature, day-ahead prices)
results/       CSV outputs (created by the scripts above)
figures/       PNG outputs (created by the scripts above)
```

## Notes for packaging/submission

- `.venv/` and `__pycache__/` are local-only (already in `.gitignore`) — exclude
  them if zipping the folder directly rather than `git archive`-ing a clean
  checkout, otherwise the zip balloons with the entire virtual environment.
- `results/` and `figures/` are committed so the report's figures/tables are
  reproducible without re-running anything, but they are also fully
  regenerable from `data/` via the pipeline above.
