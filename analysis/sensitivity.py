"""
Task-1 sensitivity study: drivers of the room-temperature OVERSHOOT.

Background
----------
Under on/off control the room (C = M_air*cp ~ 217 kJ/K, very low) free-heats
whenever the compressor is OFF. After the AC reaches T_OFF and shuts down it is
locked out for the minimum standstill (10 min). At ~4.7 kW server load that is
+1.3 K/min * 10 min ~ +13 K of uncontrolled rise -> the 34 C summer peak. The
overshoot is therefore a standstill x slew-rate effect, NOT a hysteresis effect.

This script sweeps the candidate design/model parameters one-at-a-time from the
config baseline and reports, over all four season-days:
    Tmax  : peak room temperature (the overshoot metric; band ceiling = 27 C)
    Tmin  : coldest room temperature (undershoot metric; band floor = 18 C)
    starts: total AC compressor starts (cycling metric)
    inband: % of timesteps with 18 <= T <= 27
    RHmin : minimum relative humidity (allowable floor = 14 %)

Runnable directly (path self-bootstraps):  python3 analysis/sensitivity.py
The performance map is cached to cmap_standin.pkl on first run.
"""
import os, sys, math, pickle
# Make this runnable from any launcher/cwd (no PYTHONPATH needed):
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, 'src'))
os.chdir(_REPO)  # so data/ and the cmap cache resolve from the repo root
import numpy as np
from common import config
from task1 import room, control
from task1 import simulation as sim
from task2 import cycle

CACHE = "cmap_standin.pkl"


def get_map():
    """Build (once) and cache the (T_room, T_amb) AC performance map. The map is
    cycle-side only; every controller/room sweep below reuses it unchanged."""
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    cmap = cycle.build_map()                       # full-resolution grid
    pickle.dump(cmap, open(CACHE, "wb"))
    return cmap


# snapshot the baseline so every sweep resets cleanly
_BASE = dict(T_OFF=config.T_OFF_C, T_ON=config.T_ON_C, dt=config.TIME_STEP_MIN,
             run=config.MIN_RUN_MIN, stand=config.MIN_STANDSTILL_MIN,
             vent=config.VENT_FLOW_DESIGN_M3S, mair=config.M_AIR_KG)


def set_params(T_OFF=None, T_ON=None, dt=None, run=None, stand=None,
               vent=None, mass_mult=None):
    """Patch config + the module-level constants that cache config at import
    (control step counts, sim vent flow, room air mass). mass_mult scales the
    effective thermal mass as a proxy for rack/structure heat capacity."""
    config.T_OFF_C = _BASE['T_OFF'] if T_OFF is None else T_OFF
    config.T_ON_C = _BASE['T_ON'] if T_ON is None else T_ON
    config.TIME_STEP_MIN = _BASE['dt'] if dt is None else dt
    config.MIN_RUN_MIN = _BASE['run'] if run is None else run
    config.MIN_STANDSTILL_MIN = _BASE['stand'] if stand is None else stand
    v = _BASE['vent'] if vent is None else vent
    config.VENT_FLOW_DESIGN_M3S = v
    sim.VENT_FLOW_DESIGN_M3S = v
    m = _BASE['mair'] * (1.0 if mass_mult is None else mass_mult)
    config.M_AIR_KG = m
    room.M_AIR = m
    control.MIN_RUN_STEPS = max(1, math.ceil(
        config.MIN_RUN_MIN / config.TIME_STEP_MIN))
    control.MIN_STANDSTILL_STEPS = max(1, math.ceil(
        config.MIN_STANDSTILL_MIN / config.TIME_STEP_MIN))


def metrics(cmap):
    res = sim.simulate_all(cmap)
    return (max(res[s]['T_max'] for s in config.SEASONS),
            min(res[s]['T_min'] for s in config.SEASONS),
            sum(res[s]['ac_starts'] for s in config.SEASONS),
            100 * np.mean([res[s]['frac_in_band'] for s in config.SEASONS]),
            100 * min(res[s]['phi_min'] for s in config.SEASONS))


def sweep(cmap, name, key, values):
    print("\n=== %s ===" % name)
    print("%-12s %6s %6s %7s %8s %7s" %
          (key, "Tmax", "Tmin", "starts", "inband%", "RHmin%"))
    for v in values:
        set_params(**{key: v})
        Tmax, Tmin, st, ib, ph = metrics(cmap)
        flag = "  *over 27" if Tmax > 27.5 else ""
        print("%-12s %6.1f %6.1f %7d %8.1f %7.0f%s" %
              (v, Tmax, Tmin, st, ib, ph, flag))
    set_params()


if __name__ == "__main__":
    cmap = get_map()
    set_params()
    print("BASELINE  Tmax=%.1f Tmin=%.1f starts=%d inband=%.1f%% RHmin=%.0f%%"
          % metrics(cmap))
    # ranked by observed impact on the overshoot (Tmax)
    sweep(cmap, "1. Minimum standstill time [min]  (DOMINANT)",
          "stand", [0, 5, 10, 15, 20])
    sweep(cmap, "2. Thermal-mass multiplier (rack/structure proxy)  (DOMINANT)",
          "mass_mult", [1, 2, 3, 5, 8])
    sweep(cmap, "3. Control timestep [min]  (validity check, not a fix)",
          "dt", [1, 2.5, 5, 10])
    sweep(cmap, "4. Ventilation design flow [m3/s]  (cannot rescue summer)",
          "vent", [0.15, 0.3, 0.6, 1.0, 2.0])
    sweep(cmap, "5. Hysteresis delta via T_ON  (flat on overshoot)",
          "T_ON", [22.0, 23.5, 25.5, 27.5])
