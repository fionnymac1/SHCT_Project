# Task 1 - server-room cooling: model, results, assumptions, open flags

Code in `src/`, run from repo root: `python -m src.main` (builds the AC map,
simulates the four days, writes `figures/`). Pipeline modules:
`config` (all constants + tagged assumptions) -> `data_io` (load + 30->5 min
resample) -> `flow_limits` (1.1, 1.2) -> `cycle` (VCC stand-in + (T_room,T_amb)
capacity/COP map, Hint 1) -> `room` (Ex-11 moist-air ODE) -> `control` (on/off
state machine, 1.3) -> `simulation` (driver + part-load COP_res, Hint 2) ->
`plotting`.

## Results (40 mm / Propane stand-in)
- **1.1 required cooling power = 5.00 kW** (peak server load over the 4 days).
- **1.2** V_max = Beaufort-5 (10.7 m/s) x 0.20 m2 opening = **2.14 m3/s**;
  V_min = 0.3-0.8 m3/s; ventilation usable when ambient is >~1.9 K below room.
  With a 0.2 m2 opening the acoustic cap is *slack* - free cooling is limited by
  ambient temperature, not velocity (the cap only binds for small openings).
- **1.3** band 15-18 C held 100 % of the time, all seasons. Winter = pure free
  cooling (fan only, 7.9 kWh); summer = AC all day (18.8 kWh); spring/fall mixed.
  Humidity: winter ventilation dries the room to **21 % RH** (X ~3 g/kg) -
  within allowable (>=14 %) but near the recommended floor; summer ~50-60 %.

## Owned assumptions (stated for the report)
- Temperature band 15-18 C, asymmetric; 15 C is the allowable floor, ON 17.5 /
  OFF 15.5 C, mid-band setpoint 16.5 C.
- Humidity monitored, not controlled; allowable 14-80 % RH.
- Flow cap: Beaufort-5 velocity (course slides 34-35) x assumed 0.20 m2 opening.
- Approaches: evaporator 12 K, condenser 5 K, air-side 3 K; superheat 5 K;
  subcooling 0; min pressure ratio 2 (clamped when violated).
- Fan specific power 1.0 kW per m3/s; electricity price not yet set (Task 4).
- Input data: 48 pts/day = 30-min sampling, periodic day, interpolated to 5 min.

## Modelling choices (justified)
- **Variable-capacity (modulating) cooling** to a mid-band setpoint, capped at
  cycle capacity. Fixed-speed on/off cannot hold a 15-18 C band on this small
  thermal mass (216 kg, ~217 kJ/K) at a 5-min step with a 10-min standstill -
  one forced step overshoots by many K (verified: it drives T out of range).
  Modulation IS the part-load ratio, so Hint-2 COP_res (penalising oversized
  capacity) applies directly.
- **Analytic psychrometrics** (h* = cp_a T + X(hfg0 + cp_v T), Magnus psat) in
  the inner loop: ~100x faster than per-step state_moist + brentq, and robust
  below water's triple point (the course module throws once the room dries to
  X < ~0.0038). Validated vs state_moist: dX ~ 1e-5, dT_inv ~ 0.00 K.
- **Min-pressure-ratio clamp**: at low lift p_co is raised to 2 x p_ev so the
  AC stays operable (COP penalty), closing the mild-weather cooling gap.

## OPEN FLAGS (decision/most-impactful first)
1. **Compressor cylinder count.** Provided fn is written for 2 cylinders; the
   brief says 4. This *doubles* capacity (40 mm: 7 kW vs 14 kW). The RICM60S
   datasheet is a scanned image (no text) - needs OCR or a manual read. If
   4-cyl, 40 mm is ~3x oversized -> heavy part-load penalty -> favours 30 mm.
2. **Evaporator-approach magnitude (12 K).** Sets whether the coil sits below
   the dew point: 12 K -> T_AC ~ dew point (little drying, summer 50-60 % RH);
   a smaller approach raises COP but the humidity-drift sign flips. This is the
   COP-vs-(dehumidification + comfort) lever for the Task-2 inner optimisation.
3. **Supply opening area (0.20 m2).** Makes the Beaufort-5 cap slack; a smaller
   opening makes velocity the binding constraint (course slide-35 ~10 K dT).
4. **Start/stop cycles as a Task-3 criterion.** With modulation the AC engages
   ~once/day, so this criterion barely discriminates between bores; energy and
   humidity do the discriminating. Revisit if fixed-speed staging is intended.
5. Fan-power model and electricity price (Task 4) are placeholders.
