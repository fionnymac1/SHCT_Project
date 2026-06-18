"""
Input data loading and resampling (Task 1).

Each season file holds 48 samples of a representative day. We assume 30-min
sampling over 24 h and treat the day as periodic, then linearly interpolate
onto the 5-min simulation grid. Run from the repository root.
"""
import numpy as np
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
