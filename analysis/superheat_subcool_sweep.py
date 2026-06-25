"""
Inner-cycle DOF study: justifies the FIXED superheat and the sink-bounded subcooling
used in the COP map (see common/config.py and the standard-form block in task2/cycle.py).

Why this script exists
----------------------
The task asks for "COP-optimal operation at each point in time". The cycle's only
candidate free decision variables are superheat (dT_sh) and subcooling (dT_sc) - the
evaporation/condensation temperatures are pinned by the constant-approach assumption.
This script sweeps both at a representative operating point for all three refrigerants
and shows that the COP optimum is NOT interior but sits on the constraint boundaries,
so the map can be built at fixed dT_sh/dT_sc with no per-point solver (Hint 1):

  * dT_sc: COP_inner is monotone INCREASING in subcooling for every refrigerant, so the
    optimum is the upper bound. Subcooling can only cool the liquid toward ambient, so
    that bound is  dT_sc,max = T_co - T_amb = the condenser approach (Lecture #10:
    "exploit subcooling as long as the condensation temperature must not be increased").
  * dT_sh: COP_inner is nearly flat in superheat AND refrigerant-dependent in SIGN, so
    there is no common optimum. eta_is from recip_comp_corr_SP depends only on the
    pressure ratio (= f(T_ev,T_co)), NOT on superheat - confirmed below. dT_sh is then
    set by realistic technical limits: a dry-suction minimum (no liquid into the
    compressor) below, and the discharge temperature above.

Runnable directly (path self-bootstraps):  python3 analysis/superheat_subcool_sweep.py
Writes a 2-panel figure to  superheat_subcool_sweep.png  in the repo root.
"""
import os, sys
# Make runnable from any cwd, no PYTHONPATH needed (same pattern as sensitivity.py):
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "src"))
os.chdir(_REPO)
import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless: write a PNG, do not require a display
import matplotlib.pyplot as plt
from common import config
from task2 import cycle

REFRIGERANTS = ["Propane", "R1234yf", "DimethylEther"]
T_ROOM, T_AMB = 15.0, 30.0     # representative point: T_ev = 3 C, T_co = 35 C
BORE = config.STANDIN_BORE_MM
SH_GRID = [0.5, 2, 5, 8, 10, 12, 15, 20]   # superheat sweep [K]
SC_GRID = [0, 2, 5, 8, 10]                 # subcooling sweep [K]
SC_BOUND = config.DT_APPROACH_COND_K       # sink bound = condenser approach [K]
DT_SH_FIX = config.DELTA_T_SUPERHEAT_K     # fixed superheat used in the map


def _cop_q_tdis(refr, dt_sh, dt_sc):
    p = cycle.cycle_point(T_ROOM, T_AMB, BORE, refr, dt_sh=dt_sh, dt_sc=dt_sc)
    return p["COP_inner"], p["Q_AC_kW"], p["T_dis"]


def main():
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.2))

    print("Representative point: T_room=%.0f C -> T_ev=%.0f C ; T_amb=%.0f C -> T_co=%.0f C\n"
          % (T_ROOM, T_ROOM - config.DT_APPROACH_EVAP_K, T_AMB, T_AMB + config.DT_APPROACH_COND_K))

    # (1) Confirm eta_is does not depend on superheat (the premise for "fixed superheat").
    from common import compressor_model as comp
    T_ev = T_ROOM - config.DT_APPROACH_EVAP_K
    T_co = T_AMB + config.DT_APPROACH_COND_K
    etas = [comp.recip_comp_corr_SP((T_ev, T_co, sh, SC_BOUND, BORE), "Propane")[0] for sh in SH_GRID]
    print("eta_is vs superheat (Propane): %s  -> spread %.2e (independent of superheat)\n"
          % (["%.4f" % e for e in etas], max(etas) - min(etas)))

    # (2) Superheat sweep (subcool held at the sink bound) - COP sign differs by fluid.
    print("SUPERHEAT sweep  (subcool = %.0f K):" % SC_BOUND)
    for refr in REFRIGERANTS:
        cops, qs, tds = zip(*[_cop_q_tdis(refr, sh, SC_BOUND) for sh in SH_GRID])
        axL.plot(SH_GRID, cops, marker="o", label=refr)
        d = 100 * (cops[-1] / cops[0] - 1)
        print("  %-14s COP %.3f->%.3f (%+.1f%% over %g-%g K) | T_dis %.0f->%.0f C"
              % (refr, cops[0], cops[-1], d, SH_GRID[0], SH_GRID[-1], tds[0], tds[-1]))
    axL.axvline(DT_SH_FIX, ls="--", c="0.5")
    axL.annotate("fixed\n%.0f K" % DT_SH_FIX, (DT_SH_FIX, axL.get_ylim()[0]),
                 textcoords="offset points", xytext=(4, 6), color="0.4")
    axL.set_xlabel("superheat  dT_sh  [K]"); axL.set_ylabel("COP_inner  [-]")
    axL.set_title("COP vs superheat (sign is fluid-dependent)"); axL.legend(); axL.grid(alpha=.3)

    # (3) Subcool sweep (superheat fixed) - monotone up for all; bounded by the sink.
    print("\nSUBCOOL sweep    (superheat = %.0f K):" % DT_SH_FIX)
    for refr in REFRIGERANTS:
        cops, qs, tds = zip(*[_cop_q_tdis(refr, DT_SH_FIX, sc) for sc in SC_GRID])
        axR.plot(SC_GRID, cops, marker="o", label=refr)
        i_b = SC_GRID.index(int(SC_BOUND)) if int(SC_BOUND) in SC_GRID else None
        d = 100 * (cops[i_b] / cops[0] - 1) if i_b is not None else float("nan")
        print("  %-14s COP %.3f (sc=0) -> %.3f (sc=%g, the bound)  %+.1f%%"
              % (refr, cops[0], cops[i_b], SC_BOUND, d))
    axR.axvline(SC_BOUND, ls="--", c="0.5")
    axR.annotate("sink bound\nT_co-T_amb=%.0f K" % SC_BOUND, (SC_BOUND, axR.get_ylim()[0]),
                 textcoords="offset points", xytext=(4, 6), color="0.4")
    axR.set_xlabel("subcooling  dT_sc  [K]"); axR.set_ylabel("COP_inner  [-]")
    axR.set_title("COP vs subcooling (monotone; take it to the bound)"); axR.legend(); axR.grid(alpha=.3)

    fig.tight_layout()
    out = os.path.join(_REPO, "superheat_subcool_sweep.png")
    fig.savefig(out, dpi=130)
    print("\nFigure written to %s" % out)


if __name__ == "__main__":
    main()
