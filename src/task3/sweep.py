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
        "frac_phi_allowable": float(np.mean([R[s]["frac_phi_allowable"] for s in seasons])),
        "frac_dp_recommended": float(np.mean([R[s]["frac_dp_recommended"] for s in seasons])),
        "frac_dp_allowable": float(np.mean([R[s]["frac_dp_allowable"] for s in seasons])),
        "T_min": float(min(R[s]["T_min"] for s in seasons)),
        "T_max": float(max(R[s]["T_max"] for s in seasons)),
        "phi_min": float(min(R[s]["phi_min"] for s in seasons)),
        "phi_max": float(max(R[s]["phi_max"] for s in seasons)),
        "dp_min": float(min(R[s]["dp_min"] for s in seasons)),
        "dp_max": float(max(R[s]["dp_max"] for s in seasons)),
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
    (results_by_design, df_compare); df_compare has an 'error' column (None
    on success). A combo whose simulation raises is recorded rather than
    aborting the whole sweep, so the other combos still get ranked."""
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


def save_energy_by_hour(results_by_design, path=None):
    """Long-form (refrigerant, bore_mm, season, hour, E_ac_kWh, E_vent_kWh)
    table, the resolution Task 4 needs to cost energy against real hourly
    day-ahead prices instead of a flat per-season rate. Split by equipment
    (W_comp/W_fan), not by mode, since the shared ventilator also runs during
    AC and a mode-based split would mislabel that fan energy as compressor
    energy. Written alongside the comparison CSV in main_task3.py."""
    path = path or os.path.join("results", "task3_energy_by_hour.csv")
    dt_h = config.TIME_STEP_MIN / 60.0
    rows = []
    for (refrigerant, bore_mm), R in results_by_design.items():
        for season, r in R.items():
            hour = (r["t"] // 60).astype(int) % 24
            for h in range(24):
                sel = hour == h
                rows.append({
                    "refrigerant": refrigerant, "bore_mm": bore_mm, "season": season, "hour": h,
                    "E_ac_kWh": float(np.sum(r["W_comp"][sel]) * dt_h),
                    "E_vent_kWh": float(np.sum(r["W_fan"][sel]) * dt_h),
                })
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(path, index=False)
    return path


def score_key(row):
    """Lexicographic ranking key (smaller = better):
      1. hard safety: maximise time within the allowable T, RH and dew-point
         limits (a breach is a hardware-safety failure, weighted worst);
      2. equipment reliability: maximise time within the recommended T and
         dew-point bands (RH has no recommended target, only the allowable
         bound above);
      3. minimise total AC + ventilation electricity;
      4. minimise AC start/stop cycles (compressor wear).
    Operating times are reported alongside but not separately scored, since
    they're already implied by (3)."""
    return (-min(row["frac_T_allowable"], row["frac_phi_allowable"], row["frac_dp_allowable"]),
            -min(row["frac_T_recommended"], row["frac_dp_recommended"]),
            row["E_total_kWh"], row["ac_starts_total"])


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
