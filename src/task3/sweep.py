"""
Task 3: simulate the full cooling system (Task 1's on/off controller + room
ODE, Task 2's precomputed COP/Q_AC lookup tables) for every compressor bore x
refrigerant combination, then select the most suitable design.

Pipeline per combination:
    Task 2 map on disk (results/ac_map_<refrigerant>_<bore>mm.csv)
        -> cycle.map_from_dataframe   (rebuild the interpolators, Hint 1)
        -> task1.simulation.simulate_all(cmap)   (four representative days)
        -> aggregate_metrics                      (one comparison row)

Selection (per the task sheet: energy demand, compressor start/stop cycles,
operating times, room air condition) is a simple lexicographic ranking -
keeping the room in the acceptable band matters most (it's the actual
requirement), then total electrical energy, then compressor starts (wear).
See score_key().
"""
import os
import numpy as np
import pandas as pd
from common import config, data_io, plotting
from task1 import simulation as sim
from task2 import cycle


def load_cmap(refrigerant, bore_mm):
    """Rebuild a Task-2 (T_room, T_amb) performance map from its saved CSV
    (Hint 1: interpolate the precomputed table, don't re-solve the cycle)."""
    try:
        df = data_io.load_performance_map(refrigerant, bore_mm)
    except FileNotFoundError:
        raise FileNotFoundError(
            "No saved performance map for %s / %.0f mm. Run "
            "'python src/main_task2.py' first to (re)generate results/*.csv."
            % (refrigerant, bore_mm))
    return cycle.map_from_dataframe(df)


def aggregate_metrics(refrigerant, bore_mm, R, seasons=None):
    """Collapse the per-season simulate_season() results (R = {season: r})
    into one comparison row for this (refrigerant, bore) design. seasons
    defaults to all four representative days (R.keys()); pass a shorter list
    (e.g. a single season) for the fast single-day path below."""
    seasons = list(R.keys()) if seasons is None else seasons
    return {
        "refrigerant": refrigerant, "bore_mm": bore_mm,
        "frac_T_recommended": float(np.mean([R[s]["frac_T_recommended"] for s in seasons])),
        "frac_T_allowable": float(np.mean([R[s]["frac_T_allowable"] for s in seasons])),
        "frac_phi_recommended": float(np.mean([R[s]["frac_phi_recommended"] for s in seasons])),
        "frac_phi_allowable": float(np.mean([R[s]["frac_phi_allowable"] for s in seasons])),
        "T_min": float(min(R[s]["T_min"] for s in seasons)),
        "T_max": float(max(R[s]["T_max"] for s in seasons)),
        "phi_min": float(min(R[s]["phi_min"] for s in seasons)),
        "phi_max": float(max(R[s]["phi_max"] for s in seasons)),
        "ac_starts_total": int(sum(R[s]["ac_starts"] for s in seasons)),
        "vent_starts_total": int(sum(R[s]["vent_starts"] for s in seasons)),
        "ac_min_total": float(sum(R[s]["ac_min"] for s in seasons)),
        "vent_min_total": float(sum(R[s]["vent_min"] for s in seasons)),
        "off_min_total": float(sum(R[s]["off_min"] for s in seasons)),
        "E_ac_kWh": float(sum(R[s]["E_ac_kWh"] for s in seasons)),
        "E_vent_kWh": float(sum(R[s]["E_vent_kWh"] for s in seasons)),
        "E_total_kWh": float(sum(R[s]["E_ac_kWh"] + R[s]["E_vent_kWh"] for s in seasons)),
    }


def run_design(refrigerant, bore_mm):
    """Simulate one (refrigerant, bore) design over all four representative
    days. Returns (R, metrics): R = {season: simulate_season() result dict}."""
    cmap = load_cmap(refrigerant, bore_mm)
    R = sim.simulate_all(cmap)
    metrics = aggregate_metrics(refrigerant, bore_mm, R)
    return R, metrics


def run_single_day(refrigerant, bore_mm, season):
    """Fast path for iterating on one (refrigerant, bore) design over a
    SINGLE representative day, instead of the full 9-combo x 4-season sweep.
    Returns (r, metrics): r is one simulate_season() result dict, metrics is
    the same comparison-row shape run_design() produces (so it can be
    inspected or appended to a df_compare table directly)."""
    cmap = load_cmap(refrigerant, bore_mm)
    r = sim.simulate_season(season, cmap)
    metrics = aggregate_metrics(refrigerant, bore_mm, {season: r}, seasons=[season])
    return r, metrics


def visualize_single_day(r, refrigerant, bore_mm, path=None):
    """Plot a single simulate_season() result (room T/RH, AC/VENT operation)
    via plotting.plot_season. Returns the figure path."""
    if path is None:
        path = os.path.join(
            "figures", "task3_single_%s_%.0fmm_%s.png"
            % (refrigerant, bore_mm, r["season"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    label = "%s, %.0f mm" % (refrigerant, bore_mm)
    plotting.plot_season(r, path, label=label)
    return path


def run_all_designs(refrigerants=None, bores=None, verbose=True):
    """Simulate every (refrigerant, bore) combination. Returns
    (results_by_design, df_compare): results_by_design[(refrigerant, bore_mm)]
    = R (per-season dict); df_compare = one row per combo, plus an 'error'
    column (None on success). A combo whose simulation raises (e.g. the room's
    moist-air Newton inversion can fail outside its valid range for an
    oversized/undersized AC) is recorded rather than aborting the whole sweep -
    a combo that breaks the model is informative in itself, and the other 8
    combos still need ranking."""
    refrigerants = config.REFRIGERANTS if refrigerants is None else refrigerants
    bores = config.COMPRESSOR_BORES_MM if bores is None else bores

    results_by_design = {}
    rows = []
    for refrigerant in refrigerants:
        for bore_mm in bores:
            if verbose:
                print("  running %-14s %4.0f mm ..." % (refrigerant, bore_mm))
            try:
                R, metrics = run_design(refrigerant, bore_mm)
            except Exception as exc:
                if verbose:
                    print("    FAILED: %s" % exc)
                rows.append({"refrigerant": refrigerant, "bore_mm": bore_mm,
                             "error": str(exc)})
                continue
            results_by_design[(refrigerant, bore_mm)] = R
            metrics["error"] = None
            rows.append(metrics)
    df_compare = pd.DataFrame(rows)
    return results_by_design, df_compare


def save_energy_by_season(results_by_design, path=None):
    """Long-form (refrigerant, bore_mm, season, E_ac_kWh, E_vent_kWh) table,
    one row per (design, season) -- the per-season detail Task 4 needs for
    season-specific electricity pricing, which the summed-over-all-seasons
    df_compare/aggregate_metrics table above does not retain. Written
    alongside the comparison CSV in main_task3.py."""
    path = path or os.path.join("results", "task3_energy_by_season.csv")
    rows = [{"refrigerant": refrigerant, "bore_mm": bore_mm, "season": season,
             "E_ac_kWh": r["E_ac_kWh"], "E_vent_kWh": r["E_vent_kWh"]}
            for (refrigerant, bore_mm), R in results_by_design.items()
            for season, r in R.items()]
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(path, index=False)
    return path


def score_key(row):
    """Lexicographic ranking key (smaller = better), per the task sheet's
    selection criteria in priority order:
      1. room air condition, hard safety bound first: maximise time within
         the ALLOWABLE T and RH limits (never to be crossed -- a breach here
         is a hardware-safety failure, worse than merely missing comfort);
      2. room air condition, comfort target: maximise time within the
         RECOMMENDED T band (the day-to-day operating goal);
      3. overall energy demand: minimise total AC + ventilation electricity;
      4. compressor start/stop cycles: minimise AC starts (mechanical wear).
    Operating times (ac_min/vent_min) are reported alongside for discussion
    but not separately scored (largely implied by (1)/(2)/(3))."""
    return (-min(row["frac_T_allowable"], row["frac_phi_allowable"]),
            -row["frac_T_recommended"], row["E_total_kWh"], row["ac_starts_total"])


def rank(df_compare):
    """df_compare with a 'rank' column added (0 = most suitable), sorted best
    first per score_key(). Combos that failed (see run_all_designs) are
    excluded - they have no metrics to rank on."""
    ok = df_compare[df_compare["error"].isna()] if "error" in df_compare else df_compare
    rows = sorted(ok.to_dict("records"), key=score_key)
    df = pd.DataFrame(rows)
    df["rank"] = np.arange(len(df))
    return df


def select_best(df_compare):
    """(refrigerant, bore_mm) of the top-ranked design."""
    best = rank(df_compare).iloc[0]
    return best["refrigerant"], float(best["bore_mm"])
