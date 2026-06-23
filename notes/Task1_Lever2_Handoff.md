# Task 1 — Lever #2 (Right-Sizing) Handoff

_Server-room cooling (ETH SHCT, SS2026). Session 2026-06-19. Builds on `Task1_OnOff_Handoff.md`._
_Band target this session = **18–27 °C** (ASHRAE recommended); allowable A1 = 15–32._

## Scope
Worked **lever #2** (right-size vent flow + bore) to cut band violations; resolved the ASHRAE/ACH config TODO and the compressor cylinder-count question; added vent-assist control.

## Code changes (all in `src/`; run `python src/main.py` from repo root)
| file | change |
|---|---|
| `common/config.py` | `VENT_FLOW_DESIGN_M3S = 0.15` (new DOF, τ-overshoot sizing + ASHRAE TC9.9 citation); **deleted** orphan `FLOW_RATE_ACH`/`SAFETY_MARGIN`; `STANDIN_BORE_MM 40→30`; `COMPRESSOR_N_CYL 4→2` |
| `task1/simulation.py` | VENT runs at `VENT_FLOW_DESIGN_M3S`, not the acoustic cap; assert ≤ cap |
| `task1/control.py` | `vent_feasible` now tests `V_min ≤ V_design`; added `vent_available`; **vent-assist** — VENT for partial cooling while the compressor is in its standstill (off) and ambient < room |
| `task1/flow_limits.py` | added `vent_flow_design_m3s()` + design-flow/τ lines in `summarise` |

## Results (band 18–27, Propane stand-in)
| run | winter | spring | summer | fall |
|---|---|---|---|---|
| 40 mm | 15–34 / 74% | 14–34 / 71% | 15–34 / 64% | 15–34 / 69% |
| **30 mm (current)** | 15–35 / 82% | 15–35 / 78% | 15–35 / 83% | 15–35 / 79% |

- 30 vs 40 mm: bottom fixed (operational min ~19 °C; `Tmin 15` = startup), **E_AC −12…18%**, **AC starts cut 3–5×**. **Top unchanged ~34 °C** (standstill, not capacity).
- **Vent-assist: implemented, NOT yet run.** Expected: winter top ~34→**~25 (in band)**; spring/fall partial (~28–30); summer ~unchanged (ambient too hot).

## Resolved
- **Cylinders = 2.** Moodle (L. Liebl, 11 Jun): task "4-cylinder" was a typo; use `recip_comp_corr_SP` as-is (verified — line 35 computes 2 cyl). Capacity ∝ D².
- **ACH→Beaufort TODO.** Same constraint once `A_supply` is fixed (`v = ACH·V/3600/A`); ACH is an IAQ fresh-air metric, not heat-removal → removed. Vent flow is a **design variable** capped by Beaufort-5 (**Lecture 11**, slides ~33–35 — not Lecture 10).
- **Course ventilation method** (Ex 10 / Lec 10) = blower-curve ∩ duct ΔP (Lockhart-Martinelli + `fsolve`); **not** ACH, **not** Beaufort. RICM60S = that exercise's side-channel blower; treating it as *our* ventilator is an assumption (could anchor Task-4 fan power).

## THE finding (Task 1.3 — put in the report)
**Strict on/off cannot hold 18–27 °C on this ~215 kJ/K room.** Standstill swing = `load × 600 s / C`; it exceeds the 9 K band at **load > 3.23 kW = 56% of the day**. Independent of AC power *and* of T_ON (compressor is locked out 10 min regardless). Pre-cooling can't rescue it (would need to start a 5 kW lockout at 13 °C < 15 °C floor; thermal mass too small). → vent-assist is the only mitigation (ambient-limited); **summer top is a residual limit to document, not engineer away.** (This is why the old modulating controller held 100% — no shutoff, no standstill — but modulation is off-spec.)

## Open / to work
1. **Run vent-assist**; confirm winter/shoulder tops drop; expect summer ~34 → document it.
2. **Decide Task-1.3 framing:** accept on/off excursions + argue ASHRAE allowable, vs relax an assumption (standstill / band / modulation).
3. **Refrigerant×bore coupling:** only **Propane** meets the 5 kW peak at 30 mm; R1234yf/DME (~3.6 kW) force a bigger bore → over-cool returns. Real Task-3 selection point.
4. **Winter RH 8% < 14% allowable** (AC runs more → drier). Humidity monitored, not controlled — flag in results.
5. **ODEintWarning:** AC `m_dot = Q_AC/(h−h_sink)` goes singular at over-cool → stiffness; harden the RHS (cap/clamp `m_dot`).
6. **`Tmin = 15` is the startup** (`T_INIT` < band floor) and eats into in-band % — revisit the initial condition or note it.
7. **Still owed (project):** Task 2 inner optimisation (superheat/subcool DOF, COP-optimal per step, standard DOF/obj/constraint form); Task 4 fan specific power + electricity price (placeholders); `A_SUPPLY = 0.20 m²` assumption (makes the Beaufort cap slack).

## Notes / gotchas
- **Run locally.** The OneDrive mount serves *truncated* `task1/`/`task2/` files to the sandbox; the real on-disk files are correct.
- **Rejected citations:** purkaylabs blog, massedcompute AI-FAQ (vendor / AI-generated, not citable). Use **ASHRAE TC9.9** directly.
- Pushed back on this session: the two web sources above; the "reduce AC power + turn on earlier" idea (proven it can't fix the top); and I over-promised that the smaller bore would fix the top — it didn't (corrected).
