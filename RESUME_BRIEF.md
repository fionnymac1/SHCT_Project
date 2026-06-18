# Server-Room Cooling — Resume Brief (paste to continue in a new chat)

ETH SHCT SS2026 group project. Code repo = `SHCT_Project` (git). Course
conventions live in the project instructions + memory. This brief = state
**after Task 1 was coded and verified.**

## DONE — Task 1 fully coded + verified
End-to-end run (from repo root): `python -m src.main` → builds the AC
capacity/COP map, simulates the 4 representative season-days under on/off
control, writes `figures/`. Reproduces from scratch (~30 s, the map dominates).

- **1.1** required cooling = **5.0 kW** (peak server load over the 4 days).
- **1.2** V̇_max = Beaufort-5 (10.7 m/s) × 0.20 m² opening = **2.14 m³/s**;
  V̇_min ≈ 0.3–0.8 m³/s; ventilation usable when ambient ≳ 2 K below room.
  Finding: at a realistic opening the **acoustic cap is slack** — free cooling
  is limited by ambient temperature, not velocity (cap only binds for tiny
  openings, the slides' 5 cm case).
- **1.3** band **15–18 °C held 100 %** in every season (variable-capacity
  control). Winter = pure free cooling (fan only ~7.9 kWh) but **dries to
  21 % RH**; summer = AC all day (~18.8 kWh), RH 50–60 %; spring/fall mixed.

## WHERE IT IS (`SHCT_Project/src`)
- `config.py` — all constants, tagged `[ASSUMPTION]`/`[FLAG]`, + your TODOs
- `data_io.py` — load + resample 48-pt (30-min) → 5-min, periodic day
- `flow_limits.py` — Task 1.1 + 1.2
- `cycle.py` — subcritical VCC stand-in (40 mm / Propane); COP_inner + Q_AC on
  a (T_room,T_amb) grid (Hint 1, interpolated); min-pressure-ratio clamp
- `room.py` — Exercise-11 moist-air ODE; **analytic psychrometrics** in the
  loop (fast, validated vs `state_moist`, robust below the triple point)
- `control.py` — on/off state machine (Task 1.3). `controller.py` = DEPRECATED
- `simulation.py` — driver + part-load COP_res (Hint 2)
- `plotting.py`, `main.py`
- `NOTES_Task1.md` — assumptions + open flags; `figures/` — 5 PNGs
- Env OK: CoolProp/scipy/matplotlib; refrigerants `"Propane"`,`"R1234yf"`,
  `"DimethylEther"`; `requirements.txt` re-encoded UTF-8.

## PUSHED ON / MUST RESOLVE (priority order)
1. **Control model — I changed fixed-speed on/off → variable-capacity
   MODULATING** (tracks a 16.5 °C mid-band setpoint, capped at capacity).
   Reason: fixed-speed dumping full capacity overshoots the small thermal mass
   (~214 kg) at a 5-min step + 10-min standstill — it literally drove T out of
   range. Consequence: the Task-3 criterion **"# AC start/stop cycles" barely
   discriminates** (AC engages ~1×/day). DECIDE: keep modulating, or build
   fixed-speed staging. *Biggest judgment call — ratify it.*
2. **Compressor cylinder count** — provided fn is written for **2 cylinders**;
   brief says **4** → **×2 capacity**. 40 mm ≈ 7 kW (2-cyl) vs ~14 kW (4-cyl,
   ~3× oversized → would favour 30 mm). `RICM60S specifications.pdf` is a
   **scanned image (no text)** → OCR it or read manually. Capacity numbers are
   provisional until resolved.
3. **Evaporator approach = 12 K** (stand-in) — puts the coil at the dew point;
   this is the **COP vs (dehumidification + comfort)** lever, i.e. the Task-2
   inner-optimisation variable, not yet optimised.
4. **Supply opening = 0.20 m²** (assumed) — makes the velocity cap slack;
   corroborate against **Ex.10** (your TODO).
5. **Fan specific power (1.0 kW per m³/s) + electricity price** = placeholders
   for Task 4.
- Also open (your config TODOs): humidity analysis in the results writeup;
  check the 15.5/17.5 deadband vs excessive cycling; timestep sensitivity;
  source for typical AC min run/standstill times.

## NEXT
Task 2 — cycle COP optimisation written in standard DOF/objective/constraints
form (free var ≈ superheat/subcooling/evap-approach). Task 3 — sweep 3 bores ×
3 refrigerants, select on energy / cycles / run-times / room T + humidity.
**Resolve #1 and #2 first — both change the sizing/selection.**
