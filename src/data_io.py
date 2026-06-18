"""
Input data loading and resampling (Task 1), plus save/load of the precomputed
AC performance maps (Task 2/Hint 1). Run from the repository root.

Each season file holds 48 samples of a representative day. We assume 30-min
sampling over 24 h and treat the day as periodic, then linearly interpolate
onto the 5-min simulation grid.
"""
import os
import numpy as np
import pandas as pd
import config


def _read_series(path):
    """Read a comma/newline-separated list of floats into a 1-D array."""
    with open(path, "r") as f:
        text = f.read().replace("\n", ",")
    return np.array([float(v) for v in text.split(",") if v.strip()])


def load_raw():
    """Return (server_series, {season: ambient_series}) at native 30-min res."""
    server = _read_series(config.FILE_SERVER_HEAT)
    ambient = {s: _read_series(config.FILE_AMBIENT[s]) for s in config.SEASONS}
    return server, ambient


def resample_day(series, dt_min=None):
    """
    Linear-interpolate a 48-pt/24h (30-min) series onto a dt-min grid over one
    periodic 24 h day. Returns (t_min, values) with t_min from 0 to 1440.
    """
    if dt_min is None:
        dt_min = config.TIME_STEP_MIN
    n = len(series)
    dt_src = config.DAY_MIN / n                      # 1440/48 = 30 min periodic: append the first sample at t = 1440 min so the wrap is smooth
    t_src = np.arange(n + 1) * dt_src
    v_src = np.append(series, series[0])
    t_new = np.arange(0.0, config.DAY_MIN + dt_min * 0.5, dt_min)
    return t_new, np.interp(t_new, t_src, v_src)


def diurnal_check(series):
    """Sanity helper: index of daily min/max (expect one trough, one peak)."""
    return int(np.argmin(series)), int(np.argmax(series))


def _map_path(refrigerant, bore_mm, out_dir=None):
    out_dir = config.PERFORMANCE_MAP_DIR if out_dir is None else out_dir
    return os.path.join(out_dir, "ac_map_{}_{:.0f}mm.csv".format(refrigerant, bore_mm))


def save_performance_map(df, refrigerant, bore_mm, out_dir=None):
    """Write a flattened (cycle.map_to_dataframe) AC performance map to CSV."""
    out_dir = config.PERFORMANCE_MAP_DIR if out_dir is None else out_dir
    os.makedirs(out_dir, exist_ok=True)
    path = _map_path(refrigerant, bore_mm, out_dir)
    df.to_csv(path, index=False)
    return path


def load_performance_map(refrigerant, bore_mm, out_dir=None):
    """Read back one performance map written by save_performance_map."""
    return pd.read_csv(_map_path(refrigerant, bore_mm, out_dir))


def load_all_performance_maps(refrigerants=None, bores=None, out_dir=None):
    """Return {(refrigerant, bore_mm): df} for every combination on disk."""
    refrigerants = config.REFRIGERANTS if refrigerants is None else refrigerants
    bores = config.COMPRESSOR_BORES_MM if bores is None else bores
    return {(r, b): load_performance_map(r, b, out_dir)
            for r in refrigerants for b in bores}
