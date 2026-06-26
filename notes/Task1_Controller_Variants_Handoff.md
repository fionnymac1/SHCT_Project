# Task 1.3 Control — Controller Variants Handoff (flow coupling + setpoint tuning)

_Server-room cooling (ETH SHCT, SS2026). Last updated 2026-06-25._
_Builds on `Task1_OnOff_Handoff.md` and `Overshoot_Sensitivity_Handoff.md` — read those first._

Scope of this session: three controller variants on top of the baseline two-flow
on/off (Task1_OnOff), plus the systematic setpoint-tuning sweep. All knobs are
**flags owned by `control.py`, default OFF = today's behaviour**, revert by
restoring `control.py` from its copy.

---

## What was tested / where

| Variant | Switch (in `control.py`) | Idea |
|---|---|---|
| Baseline | `VENT_USES_AC_FLOW=False`, `SETPOINT_SCHEDULE=False` | two flows (damper/VFD): gentle 0.15 m³/s VENT, high per-combo AC recirc flow |
| **V1 single-flow** | `VENT_USES_AC_FLOW=True` | "no damper" — one fan operating point, VENT forced to the AC recirc flow |
| **V2 fixed setpoints** | `SETPOINT_SCHEDULE=True`, `SCHED_K=0`, vary `SCHED_G` | lower the whole relay band by a constant `G` [K], all seasons |
| **V3 ambient schedule** | `SETPOINT_SCHEDULE=True`, `SCHED_G=0`, vary `SCHED_T_STAR`,`SCHED_K` | lower the band only when `T_amb>T*`, by `K·(T_amb−T*)`, clamped `T_OFF≥18` |
| V4 combo (UNTESTED) | `SCHED_G>0` AND `SCHED_K>0` | union of V2+V3 — predicted best, never run (see Next steps) |

Code touched (all revertable):
- `control.py`: `VENT_USES_AC_FLOW` + `vent_flow_m3s()`; `SETPOINT_SCHEDULE`,
  `SCHED_G/SCHED_K/SCHED_T_STAR/SCHED_T_OFF_FLOOR` + `setpoints(T_amb)`; `decide()`
  now reads `setpoints(T_amb)` instead of the raw `config.T_*` constants.
- `simulation.py`: `V_vent` hook reads `control.vent_flow_m3s(...)` via `getattr`
  (so reverting `control.py` alone restores the two-flow baseline; 3 VENT refs use `V_vent`).
- New `src/main_setpoint_sweep.py`: the tuning sweep (Arm A fixed / Arm B schedule),
  ranks by the Task-3 lexicographic key, writes `results/setpoint_sweep_*.csv`.

---

## Physics / diagnoses (for Methods + Uncertainties)

- **Room time constant** `τ = M/(ρ·V)` (M≈216 kg, ρ=1.19). Baseline VENT 0.15 m³/s →
  τ≈1200 s = **4 timesteps** (gentle, can't overshoot in one step). Single-flow VENT
  = AC recirc flow (Propane: 0.61/1.08/1.69 m³/s for 30/40/50 mm) → τ ≈ **1 step or
  less** → one 5-min VENT step drives the room most of the way to ambient.
- **Single-flow worst forced VENT step** (from T_ON=23.5, coldest ambient, via
  `flow_limits.vent_step_landing_C`): winter **bore30 →11.0 °C, bore40 →6.1, bore50
  →3.3** (40/50 breach the 10 °C hard limit). Confirms `Overshoot_Sensitivity`'s
  "high flow wrecks winter" row at the controller level.
- **Standstill swing** = `Q_peak·t_standstill/(M·cp)` = 5 kW·600 s/217 kJ/K ≈
  **13.9 K** (printed by the sweep) vs the **9 K** recommended band. Setpoints **shift
  the band, they cannot shrink the swing** — this caps any setpoint tuning. (Same
  mechanism as `Overshoot_Sensitivity`: standstill-lockout × slew-rate.)
- **Peak is set by `T_OFF` alone** (peak ≈ T_OFF + standstill climb); `T_ON_AC`/`T_ON`
  don't affect the locked-standstill peak. **AC cycling** is set by the deadband
  *width* (`T_ON_AC − T_OFF`), which a rigid shift never changes → starts stay flat.

---

## Results

### V1 single-flow, four seasons (Propane 30 mm, `main.py`)

| season | Tmin | Tmax | Trec% | Tall% | RHmin | AC st/min | VENT st/min | E_AC/E_v kWh |
|---|---|---|---|---|---|---|---|---|
| winter | 12.5 | 29.2 | 80 | 100 | **11%** | 24 / 670 | 36 / 180 | 10.38 / 1.83 |
| spring | 14.6 | 29.7 | 87 | 100 | **14%** | 25 / 710 | 40 / 225 | 10.97 / 2.29 |
| summer | 15.0 | 34.3 | 83 | 100 | 25% | 37 / 1050 | 11 / 55 | 17.56 / 0.56 |
| fall | 15.0 | 28.1 | 94 | 100 | 19% | 28 / 625 | 40 / 360 | 9.74 / 3.66 |

RHmin 11–14% **breaches the 20% allowable floor** (winter/spring). Winter runs the
compressor 670 min (a free-cooling season made compressor-heavy by the VENT crash).

### Setpoint sweep, single-flow, Propane 30 mm (ranked, Task-3 key)

| tag | Trec% | Tall% | Tmin | Tmax | RHmin | E_tot kWh | AC st | VENT st |
|---|---|---|---|---|---|---|---|---|
| **fixed G=1.0** | **92.0** | 100 | 12.2 | 33.7 | 11% | 59.51 | 122 | 106 |
| fixed G=2.0 | 90.7 | 100 | 12.0 | 32.6 | 12% | 60.16 | 108 | 101 |
| sched T*=24 K=0.5 | 88.7 | 100 | 12.5 | **29.8** | 11% | 57.23 | 110 | 123 |
| sched T*=24 K=1.0 | 88.0 | 100 | 12.5 | 29.8 | 11% | 57.26 | 110 | 123 |
| sched T*=28 K=1.0 | 87.8 | 100 | 12.5 | 31.9 | 11% | 57.48 | 111 | 127 |
| sched T*=28 K=0.5 | 87.7 | 100 | 12.5 | 31.9 | 11% | 57.40 | 111 | 127 |
| fixed G=3.0 | 85.9 | 100 | 11.5 | 31.2 | 13% | 60.28 | 96 | 98 |
| fixed G=0.0 (today) | 85.8 | 100 | 12.5 | 34.3 | 11% | 56.98 | 114 | 127 |

(E_tot = 4-season total. Best fixed 92.0 vs best sched 88.7 → **schedule loses by 3.4 pts Trec**.)

---

## Findings / verdicts

1. **Single-flow (no damper) is strictly worse than two-flow.** It kills free
   cooling in cold seasons (one VENT step crashes the room), **breaches the RH
   floor**, and thrashes (winter 670 min AC, 24+36 starts). Its only benefit is
   deleting the damper/VFD hardware. **Keep two flows.** (See V1 table; τ argument.)

2. **A flat ~1 K downshift is the best comfort controller in this family.**
   fixed G=1 → **Trec 92.0%** vs baseline 85.8% (**+6 pts**). The win is **mild-season
   centering**, NOT summer overshoot: today's setpoints (T_OFF 21.5 / T_ON_AC 25) sit
   too high in 18–27, so the room rides the upper half and clips 27 in spring/fall.
   G>2 over-cools → Trec falls again (interior optimum ≈ G=1; refine 0.5–1.5).

3. **The ambient schedule (V3) loses on comfort, wins a different objective.** It
   forfeits the mild-season centering (does nothing below T*), so −3.4 pts Trec vs the
   flat shift. BUT it gives the **lowest Tmax (29.8 °C, ~5 K under the 35 hard limit)
   at the lowest energy (57.2 kWh)** because it doesn't over-cool the mild seasons. So:
   **fixed G=1 = best comfort; sched T*=24 = best summer-safety-per-kWh.** The winner is
   **objective-dependent** — state which criterion you optimise.

4. **Setpoints cannot fix winter.** Tmin 12.5 / RHmin 11% are flat across every row —
   the cold-season single-flow VENT crash is a *flow* problem, not a setpoint one.

5. **Untested but predicted to dominate: V4 combo** `G=1 + K (T*=24)`. G and K act in
   different regimes (G everywhere incl. mild seasons; K only above T*), so they stack:
   ~92% Trec (G's centering) AND ~30 °C Tmax (K reaches the 18 floor in summer). Likely
   beats both isolated winners. Verify (sim is nonlinear).

---

## For the report

- **Write the tuning as the lecture-3 standard-form optimisation:** DOF = {SCHED_G,
  SCHED_K, SCHED_T_STAR}; objective = lexicographic max Trec% → max Tallow% → min
  E_total → min AC starts; constraints = rigid shift preserves ordering + deadband,
  `T_OFF ≥ 18`.
- **Justified simplicity (graded):** the fixed shift beats the ambient schedule, so
  adopt the simpler model — and *say why* (the schedule's gain is negative).
- **State the objective explicitly:** the "best controller" flips between fixed-G and
  the schedule depending on whether you weight comfort, hard-limit margin, or energy.
- **Uncertainties:** standstill (10 min) and thermal mass (air-only 216 kg) are FIXED
  by the task/§5 but *conservative* (real rack capacitance would damp the peak); the
  swing > band result means recommended-band compliance during a peak-load standstill
  is infeasible by setpoints alone. Single-flow vs two-flow is a hardware (damper/VFD)
  decision with a clear cost (loses free cooling + RH floor in 3/4 seasons).
- **Clean figure to make:** the sweep's Trec vs Tmax trade across rows (fixed arm vs
  schedule arm) — shows the objective-dependence in one plot.

---

## Next steps (priority order)

1. **Run V4 combo arm** (`G∈{1,1.5} × K∈{0.5,1.0}` at `T*=24`) — the predicted winner.
   *(Offered to add a `combo` arm to `main_setpoint_sweep.py`.)*
2. **Re-run everything on `FLOW_MODE='two'`** (top of `main_setpoint_sweep.py`). Two-flow
   fixes winter; a fixed ~1 K shift on top is likely the best controller, period.
3. Refine the fixed arm around G=0.5–1.5.
4. Optional new DOF: **deadband width** (decouple `T_OFF` from `T_ON_AC`) — the only
   lever that moves AC start/stop cycles, which the rigid shift leaves flat (~96–122).
5. Winter RH-floor breach (11% < 20%) + VENT crash remain open — need two-flow / lower flow.

---

## Bugs found & fixed this session (so they don't recur)

- `config.T_BAND_LOW_C` was **referenced but never defined** (after the RECOMMENDED/
  ALLOWABLE rename) in `flow_limits.vent_overshoot_ok` + `simulation.py`. Latent because
  the gentle baseline never trips the VENT-overshoot guard; single-flow trips it at once
  → `AttributeError`. **Fixed:** defined `T_BAND_LOW_C/T_BAND_HIGH_C` in `config.py`.
- `main.py` printed `frac_in_band` (renamed away) → `KeyError`, plus a hidden 15-args-into-
  13-slots mismatch. **Fixed:** print uses `frac_T_recommended`/`frac_T_allowable`.
- `results/ac_map_*.csv` were **stale** (T_room only 8–13; room runs 15–35). **Fixed:**
  regenerated via `main_task2.py` (now 8–37). `task3_design_comparison.csv` still holds
  **git merge-conflict markers** — regenerate on next `main_task3.py`.

## How to run / revert

- `python src/main.py` — single combo, builds its map in-process (immune to stale maps).
  Set `control.VENT_USES_AC_FLOW` / `SETPOINT_SCHEDULE` to pick the variant.
- `python src/main_setpoint_sweep.py [refrigerant] [bore] [arm]` — sweep; `arm∈{fixed,sched,both}`;
  `FLOW_MODE` at top toggles single/two-flow.
- **Revert to baseline:** restore `control.py` from its copy (or set all flags False).

## Gotchas (same as prior handoffs)

- OneDrive serves **truncated/null-padded** copies of some `src` files to the Linux
  sandbox; file-tool overwrites of an existing file can null-pad. The real on-disk files
  (and `Edit`/heredoc writes) are correct. Regenerate maps via `main_task2.py` before
  `main_task3.py` or `main_task2_viz.py` (the viz only *loads* saved maps).
- Compressor fn: `recip_comp_corr_SP(param, refrigerant)`; min-pressure-ratio clamp active on much of the map.
