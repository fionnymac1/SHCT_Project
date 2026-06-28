"""
Outer control-tuning sweep (Task-1 exploration): does ambient-scheduling the
relay setpoints improve on a flat shift? Searched, not guessed -- this is what
generates the "Setpoint placement" sensitivity figure in the report.

  DOF        : SCHED_G (constant band shift), SCHED_K (ramp slope), SCHED_T_STAR
  objective  : Task-3 lexicographic key (max Trec%, then Tallow%, then min
               E_total, then min AC starts)
  constraints: rigid shift preserves ordering + deadband; T_OFF >= SCHED_T_OFF_FLOOR

Two arms: A fixed setpoints (SCHED_K=0, vary the constant shift G); B ambient
schedule (SCHED_G=0, vary T*/K). Adopt B only if it beats A's best by enough
to justify the extra knobs (it didn't -- the adopted design is arm A, G=1 K).

Run from the repo root (after main_task2.py has rebuilt results/*.csv):
    python src/main_setpoint_sweep.py [refrigerant] [bore] [arm]
arm in {fixed, sched, both} (default both); each point is a full four-season
sim, so the full grid takes minutes.
"""
import sys
import warnings
import numpy as np
from common import config, data_io
from task1 import control
from task1 import simulation as sim
from task3 import sweep

warnings.simplefilter("ignore")     # cold-season VENT-overshoot warnings are expected here

REFRIGERANT = sys.argv[1] if len(sys.argv) > 1 else config.STANDIN_REFRIGERANT
BORE = float(sys.argv[2]) if len(sys.argv) > 2 else config.STANDIN_BORE_MM
ARM = sys.argv[3] if len(sys.argv) > 3 else "both"
FLOW_MODE = "two"                   # "two" = adopted two-flow (damper) controller; "single" = no-damper test

G_GRID = [0.0, 1.0, 2.0, 3.0]                   # arm A: constant downward shift [K]
TSTAR_GRID = [24.0, 28.0]                       # arm B: ramp breakpoint [degC]
K_GRID = [0.5, 1.0]                             # arm B: ramp slope [K/K]


def standstill_swing_K():
    """Upper-bound room rise during one locked standstill at peak load -- the
    ceiling on what ANY setpoint tuning can do (it shifts the band, not the swing)."""
    server_raw, _ = data_io.load_raw()
    q_peak = float(np.max(server_raw))
    t = config.MIN_STANDSTILL_MIN * 60.0
    return q_peak * t / (config.M_AIR_KG * config.CP_AIR_KJ_KGK)


def run_point(cmap, G, K, Tstar):
    control.VENT_USES_AC_FLOW = (FLOW_MODE == "single")
    control.SETPOINT_SCHEDULE = True
    control.SCHED_G, control.SCHED_K, control.SCHED_T_STAR = G, K, Tstar
    R = {s: sim.simulate_season(s, dict(cmap)) for s in config.SEASONS}
    return sweep.aggregate_metrics(REFRIGERANT, BORE, R)


def key(m):
    # smaller = better: max Trec%, then max Tallow%, then min energy, then min AC starts
    return (-round(m["frac_T_recommended"], 4), -round(m["frac_T_allowable"], 4),
            round(m["E_total_kWh"], 3), m["ac_starts_total"])


def show(tag, m):
    print("%-22s | Trec=%5.1f%% Tallow=%5.1f%% | Tmin=%5.1f Tmax=%5.1f RHmin=%3.0f%% | "
          "E=%6.2f kWh | ACst=%3d VENTst=%4d"
          % (tag, 100 * m["frac_T_recommended"], 100 * m["frac_T_allowable"],
             m["T_min"], m["T_max"], 100 * m["phi_min"], m["E_total_kWh"],
             m["ac_starts_total"], m["vent_starts_total"]), flush=True)


def main():
    cmap = sweep.load_cmap(REFRIGERANT, BORE)
    swing = standstill_swing_K()
    band = config.T_RECOMMENDED_HIGH_C - config.T_RECOMMENDED_LOW_C
    print("=" * 96)
    print("Setpoint-tuning sweep | %s %.0fmm | flow=%s" % (REFRIGERANT, BORE, FLOW_MODE))
    print("Standstill swing at peak load ~ %.1f K vs recommended band = %.0f K  ->  "
          "setpoints SHIFT the band, they cannot SHRINK the swing." % (swing, band))
    print("=" * 96)

    rows = []
    if ARM in ("fixed", "both"):
        print("\n--- ARM A: fixed setpoints (SCHED_K=0, vary constant shift G) ---")
        for G in G_GRID:
            try:
                m = run_point(cmap, G, 0.0, 24.0); m["_tag"] = "fixed G=%.1f" % G
                show(m["_tag"], m); rows.append(m)
            except Exception as e:
                print("fixed G=%.1f FAILED: %s" % (G, e), flush=True)

    if ARM in ("sched", "both"):
        print("\n--- ARM B: ambient schedule (SCHED_G=0, vary T*, K) ---")
        for Tstar in TSTAR_GRID:
            for K in K_GRID:
                try:
                    m = run_point(cmap, 0.0, K, Tstar); m["_tag"] = "sched T*=%.0f K=%.1f" % (Tstar, K)
                    show(m["_tag"], m); rows.append(m)
                except Exception as e:
                    print("sched T*=%.0f K=%.1f FAILED: %s" % (Tstar, K, e), flush=True)

    if not rows:
        print("no points completed."); return
    rows.sort(key=key)
    print("\n=== RANKED (best first; Task-3 lexicographic) ===")
    for m in rows:
        show(m["_tag"], m)

    fixed = [m for m in rows if m["_tag"].startswith("fixed")]
    sched = [m for m in rows if m["_tag"].startswith("sched")]
    if fixed and sched:
        bf, bs = min(fixed, key=key), min(sched, key=key)
        d = 100 * (bs["frac_T_recommended"] - bf["frac_T_recommended"])
        print("\nbest FIXED  : %-16s Trec=%.1f%% Tallow=%.1f%%" % (bf["_tag"], 100 * bf["frac_T_recommended"], 100 * bf["frac_T_allowable"]))
        print("best SCHED  : %-16s Trec=%.1f%% Tallow=%.1f%%" % (bs["_tag"], 100 * bs["frac_T_recommended"], 100 * bs["frac_T_allowable"]))
        print("schedule gain over best fixed = %+.1f pts Trec  ->  adopt the ambient schedule ONLY if this justifies the extra knobs." % d)

    import pandas as pd
    df = pd.DataFrame(rows)
    out = "results/setpoint_sweep_%s_%.0fmm_%s.csv" % (REFRIGERANT, BORE, FLOW_MODE)
    df.to_csv(out, index=False)
    print("\nWrote %s" % out)


if __name__ == "__main__":
    main()
