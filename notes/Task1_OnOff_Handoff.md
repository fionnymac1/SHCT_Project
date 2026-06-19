# Task 1.3 Control — On/Off Handoff Brief

_Server-room cooling (ETH SHCT, SS2026). Last updated 2026-06-19._

## What changed this session (all in `src/task1/`)

- **Killed the capacity modulation → true on/off.** Previously the AC was
  modulated to a mid-band setpoint — off-spec. Now: AC on = full `Q_AC` at the
  operating point, VENT on = full design flow, off = 0. Files: `simulation.py`,
  `room.py`.
- **Re-keyed COP_res.** Under on/off `Q_cool = Q_AC`, so the old
  `PLR = Q_cool/Q_AC = 1` silently deleted the Hint-2 part-load penalty. Now
  `PLR = Q_server/Q_AC` (demand/capacity). `simulation.py`.
- **`room.rhs` recomputes cooling at live enthalpy** so VENT self-limits at
  ambient (prevents a frozen ~25 kW rate integrating to −30 °C in one winter
  step).
- **Cycling limits gate the COMPRESSOR only.** The 5/10-min min-run/standstill
  are AC-unit limits (pressure equalisation + oil return), not fan limits.
  VENT/OFF now switch freely. `simulation.py` tracks `comp_run`/`comp_idle`
  timers; `control.py` rewritten (`decide` signature changed).

## State

- Runs via `python -m src.main`. Stand-in: 40 mm Propane, `Q_AC ≈ 7.5 kW` vs
  2–5 kW server load. Config unchanged.
- **Gotcha:** the OneDrive mount serves stale/truncated files to the sandbox —
  stage a clean copy in `/tmp` to actually run; the real files on disk are
  correct.

## Current results (true on/off, compressor-only limits)

| season | T range (°C) | in 15–18 |
|--------|--------------|----------|
| winter | 3.1 – 24.4   | 18%      |
| spring | 6.9 – 27.9   | 27%      |
| summer | 9.6 – 33.3   | 23%      |
| fall   | 10.7 – 28.1  | 35%      |

(The modulation version held 100% in band — but was off-spec.)

## Pushed back on / still open

- The band collapse is **physics, not a bug** (verified step-by-step). With the
  fan freed, residual swing decomposes cleanly:
  - up-overshoot (vent seasons) = *one timestep of heating above T_ON*:
    17.5 + 5 kW·300 s / 217 kJ/K ≈ 24.4 °C;
  - down-crash = *one timestep of full-capacity cooling* (~10 K);
  - summer's 33 °C = the genuine compressor 10-min standstill (unavoidable while
    AC-bound).
  - `m·cp ≈ 217 kJ/K` (air only, fixed by the task).
- **Threshold/deadband tuning does nothing** to these.
- **15–18 °C band is self-imposed** (tagged `[ASSUMPTION]`, not given by the
  task). ASHRAE A1 allowable is 15–32 °C.

### Next levers (none done yet — awaiting decision)

1. **Timestep sensitivity** `dt ∈ {5, 2, 1, 0.5} min` — tests whether "5-min
   adequate" survives contact with on/off. *Recommended first move* (one config
   change).
2. **Right-size capacity** — vent design flow well below the acoustic cap; bore
   nearer the load. Ties into Task 3 selection.
3. **Redefine the acceptable band** — rescues the top overshoots only, not the
   sub-15 °C crashes.

### Older flags still live

- Compressor cylinder count 2-vs-4 (provided fn is 2-cyl, config says 4 — flips
  bore choice).
- Evaporator approach = 12 K (the COP-vs-dehumidification lever for Task 2).
- Fan specific power + electricity price are placeholders (Task 4).
