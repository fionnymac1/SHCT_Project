# Overshoot Sensitivity — Handoff (Task 1)

Status: root cause of the ~34 C room-temperature overshoot identified and quantified.
Reusable sensitivity harness committed. Open items below.

## What was done / where
- Built a one-at-a-time sensitivity harness: `analysis/sensitivity.py`.
  Run directly (path self-bootstraps, no PYTHONPATH): `python3 analysis/sensitivity.py`.
  First run builds the full-res AC map (~1–2 min) and caches `cmap_standin.pkl`; later runs are fast.
- Metrics reported over all 4 season-days: peak T (overshoot), min T (undershoot),
  AC starts (cycling), % in band (18–27), min RH (floor = 14 %).

## Root cause (confirmed in sim, identical all 4 seasons)
Overshoot = **standstill-lockout × slew-rate**, NOT hysteresis.
AC cools to T_OFF and shuts off → room free-heats at Q_srv/C ≈ 4.7 kW / 217 kJ/K ≈ +1.3 K/min
→ compressor locked out for the 10-min standstill → +13 K. Vent-assist (0.15 m³/s) ≈ 1–2 kW,
can't offset it; in summer ambient ≥ room so no vent rescue → binding 34 C peak.
Side effect: baseline **RH_min = 11 % < 14 % floor** (aggressive cycling over-dries the room).

## Sensitivity results (peak T over 4 days; baseline = 34.5 C)
| Parameter | Effect on peak | Note |
|---|---|---|
| Min standstill (0/5/10/15/20 min) | 28 / 28 / 34.5 / 41 / 47 | dominant — but FIXED by task |
| Thermal mass (×1/2/3/5) | 34.5 / 28 / 25.8 / 24.5 | dominant — but FIXED by §5 model |
| Timestep (1/5/10 min) | 34.6 / 34.5 / 34.9 | flat → overshoot is PHYSICAL, not numerical |
| Ventilation flow (0.3/1.0/2.0) | 34.1 / 35.2 / 52.7 | can't rescue summer; high flow wrecks winter |
| Hysteresis delta (1–6 K) | 34.6 → 34.6 | FLAT — not the lever (my first instinct was wrong) |
| Bore (30/40/50 mm) | 34.5 / 33.8 / 35.1 | flat on peak; starts 116→255, Tmin 15→12.5 |
| Band placement (shift down 2 K) | 30.9 vs 34.5 | trades overshoot for undershoot |

## TUNABLE vs FIXED (the key distinction)
NOT tunable (task constraints / fixed model) — these EXPLAIN the overshoot, they are not fixes:
- **Minimum standstill (10 min)** — given as a constraint. Action: verify the assumed value vs
  "typical AC standstill times"; put in Methods + Uncertainties (shorter → smaller overshoot).
- **Thermal mass (air-only, 216 kg)** — fixed by §5. Action: Uncertainties note that real
  rack/structure capacitance would damp the peak → the model is conservative. Do NOT silently add mass.

Tunable (where the actual fix must come from):
- **Control STRATEGY** (highest value): the AC shuts off into the load ramp, then gets locked out.
  Design the strategy so the compressor does NOT shut off during the high-load window
  (e.g. block shutoff when the resulting standstill rise would exceed headroom; or pre-cool to the
  band floor before the daily load peak). This is the real within-constraints lever.
- **Capacity / sizing (bore, refrigerant)** — co-design with the strategy so duty ≈ 100 % through
  the peak (run continuously, never reach T_OFF → no lockout). Bore alone is flat on the peak.
- **Threshold placement (T_OFF/T_ON)** — shifting the band down lowers the peak but risks the
  18 C floor; bounded lever.
- **Evaporator approach (Task 2 variable)** — affects coil temp → condensation → the RH-floor
  violation; tune alongside the COP optimisation.
- Ventilation flow — bounded; cannot fix summer, hurts winter if raised. Leave throttled.

## Open items pushed on
1. Redesign the on/off control strategy to avoid shutoff-into-lockout during peak load (+ sizing co-design). PRIMARY.
2. Fix the RH_min = 11 % < 14 % violation (control strategy + evap approach).
3. Report framing: standstill & thermal mass → Methods (justify values) + Uncertainties (conservatism), not "tuning".
4. If structural thermal mass is ever modelled, do it as a SEPARATE sensible capacitance, not M_air×k (the harness uses the crude proxy).

## Gotchas
- OneDrive leaves truncated/null-padded placeholders of some src files in the Linux sandbox mount,
  and the file-tool→outputs mount can null-pad writes. Rebuild a clean tree in `$HOME` via bash and
  verify (no null bytes + compiles) before running. bash→OneDrive writes were reliable.
- Compressor fn confirmed: `recip_comp_corr_SP(param, refrigerant, transcrit=False)`.
- Min-pressure-ratio clamp (p_co/p_ev≥2) is active on ~81 % of the Propane map → COP penalty worth noting.
