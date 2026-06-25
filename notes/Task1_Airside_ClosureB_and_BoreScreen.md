# Task 1 — Air-side closure (A→B), fan sizing, and the bore screen

Working note. Captures the reasoning chain and the code changes made, from the
per-timestep causal chain to the `q_peak` bore-adequacy screen.

---

## 0. The causal chain (one direction, no circularity)

```
(T_room, T_amb) + approach EVAP/COND
   → T_ev, T_co
   → [compressor: ṁ_ref, η_is] → q_evap, w_comp
   → Q_AC = ṁ_ref·q_evap , COP            ← REFRIGERANT side (ṁ_air NOT involved)
   → [+ fixed ṁ_air]  T_AC = T_room − Q_sens/(ṁ_air·cp)   ← AIR side
   → check T_AC ≥ T_ev + AIR
   → humidity (condensation two-case)
```

Two **separate mass flows**, two jobs, meeting only at `T_AC`:
- **ṁ_ref** (compressor) sets **how much heat** is removed: `Q_AC = ṁ_ref·q_evap`.
- **ṁ_air** (fan) sets **at what temperature** the air leaves the coil: `T_AC`.

`Q_AC` does **not** depend on `ṁ_air` (T_ev is fixed by the approach), so the chain
is acyclic: `T_ev → Q_AC → T_AC`. The room temperature is driven by `Q_AC`; `T_AC`
is needed only for humidity and the air-flow consistency check.

---

## 1. Cycle / approach formulation (what is DOF, what is constant)

Course standard form (Lecture 3 / **Exercise 3**, verified): the decision
variables are **T_ev, T_co**; superheat and subcooling are **given constants**;
the approach temperatures are **minimum-pinch inequality constraints**.

Because COP is monotone (↑ in T_ev, ↓ in T_co), the approach constraints are
**active** at the optimum → the constant-approach model **is** the solved
optimum. Verified: `cycle_opt.optimize_cop` (SLSQP) reproduces `cycle.cycle_point`
at the unclamped points (COP identical); the `Πmin` clamp regime is ~0.8% off.

**Approach values (decided, in `config.py`):** they are **reservoir-inlet → plateau**
differences (the 0-D model knows T_room, T_amb), NOT the local pinch. The course
0.5–5 K pinch is realised as the **AIR** approach.

| symbol | value | meaning / justification |
|---|---|---|
| `DT_APPROACH_EVAP_K` | 12 K | T_room − T_ev. DX evaporator return-air→evap TD (field 8–20 K). |
| `DT_APPROACH_COND_K` | **10 K** (was 5) | T_co − T_amb. Air-cooled field 7–12 K. 5 K + 5 K subcool ⇒ T_3=T_amb (zero cold-end pinch, unphysical); 10 K gives a realistic 5 K liquid-to-ambient approach. **COP ≈ −15% vs the old 5 K** in warm weather — own it. |
| `DT_APPROACH_AIR_K` | 3 K (added) | T_AC − T_ev, cold-end pinch (= course 0.5–5 K). Was referenced but **undefined** → `AttributeError`. |
| `DELTA_T_SUPERHEAT_K` | 5 K | dry-suction min; COP ~flat in superheat (fluid-dependent sign). |
| `DELTA_T_SUBCOOL_K` | 5 K | ≤ sink bound (T_co − T_amb); COP monotone ↑ in subcool. |

---

## 2. Air side: closure A → closure B

Identity on the evaporator (definitional): **EVAP = glide + AIR**, i.e.
`(T_room − T_ev) = (T_room − T_AC) + (T_AC − T_ev)` = 9 + 3 = 12 K.
`glide` is **not free**: `glide = Q_sens/(ṁ_air·cp)`. So once EVAP and Q are set,
only **one** of {glide, AIR, ṁ_air} is free — fixing two over-determines the coil.

- **Closure A (old):** fix `T_AC = T_ev + 3`, let `ṁ_air` float. Hides the shared-fan
  constraint (the implied AC flow varied 0.36–0.53 m³/s, ≠ the VENT flow).
- **Closure B (new):** fix `ṁ_air` (the fan), **derive** the coil outlet from the
  energy balance + saturation line, floored at the air pinch:

  `h_sink = h_room − Q_AC/ṁ_air`; (T_AC, X_sink) on the saturation line if
  condensing, else dry at X_room; **T_AC ≥ T_ev + AIR** (else the air would need an
  infinite coil → fan undersized at that point).

Implemented in `room.coil_outlet_B` (precomputed saturation table, wet/dry + floor)
and used in the AC step of `simulation.py`. The RHS now uses the **fixed** flow
(`Q_cool = ṁ_air·(h_−h_sink)`, self-limiting) instead of a floating one.

**Physical consequence:** the bigger fixed fan gives a **warmer** coil outlet
(~14 °C at 22 °C/60 %, just above the dew point) → **less over-drying** than closure
A — favourable for the binding low-RH risk.

---

## 3. Fan sizing — one ventilator, two flows

A single fixed flow is **impossible** (verified):
- free cooling needs **V ≤ ~0.17 m³/s** or a worst winter step overshoots the low band;
- the AC needs **V ≥ ~0.5 m³/s** or T_AC < T_ev + AIR.

No overlap → **one fan, two speeds** (intake damper or VFD; both = "one ventilator",
§5 coupling respected). `[task 4]` fan power: damper ≈ near-full at low flow; VFD ≈ flow³.

| | value | basis |
|---|---|---|
| `VENT_FLOW_DESIGN_M3S` | 0.15 | passes `flow_limits.vent_overshoot_ok` (lands 21 °C worst winter step). |
| `AC_FAN_FLOW_M3S` | **0.62** | `= maxQ_AC,on /(ρ·cp·(EVAP−AIR))`, **pinned to the sim** `maxQ_AC,on = 6.6 kW`. Turndown 0.62/0.15 = 4.1×, velocity 3.1 m/s → feasible. |

Sizing rule:  **ṁ_air ≥ Q_AC,max / (ρ·cp·(EVAP − AIR)) = Q_AC,max / (ρ·cp·9)**.

The `fanU` (`ac_fan_undersized_steps`) counter exists because Q_AC,max-when-ON is a
**sim output** (the AC runs at high-capacity points: overshoot **and** cold-ambient
supplementing). Provisional sizing on the screen point (5.54) floored ~30 % of AC
steps; re-pinning to the sim max (6.6 → 0.62) drove **fanU → 0**.

---

## 4. The bore-adequacy screen (`q_peak`)

`q_peak` = max server load = **5.0 kW** (Task 1.1). It is a **sizing screen**, not an
operating point — under on/off the AC runs flat-out and meets the lower load by
cycling.

**Principle.** Worst hour = hottest ambient (35 °C summer): AC capacity is weakest and
free cooling is useless (ambient > room). The AC flat-out must reject `q_peak` within
the band. Capacity rises with T_room, so the room settles at the balance temp where
`Q_AC(T_bal, 35) = q_peak`:

**bore adequate ⟺ T_bal ≤ 27 °C ⟺ Q_AC(27, 35) ≥ q_peak.**

`Q_AC(27, 35)` [kW], `*` = passes:

| | D30 | D40 | D50 |
|---|---|---|---|
| **Propane** | 5.54 * | 9.85 * | 15.40 * |
| **R1234yf** | 4.11 | 7.31 * | 11.42 * |
| **DimethylEther** | 3.99 | 7.09 * | 11.08 * |

**Finding:** only **Propane fits bore 30**; R1234yf and DME need bore ≥ 40 (lower
volumetric capacity). Propane@30 balances the 5 kW peak at ~24.5 °C — right-sized.
Bigger bores are increasingly oversized → part-load COP penalty (D50 ≈ −14 % at peak,
worse at mean load) **and** infeasible fan turndown (D50 would need ṁ_air ≈ 1.4 m³/s).
Part-load, screen, and fan feasibility all converge on **bore 30**.

*(Not yet wired into selection — `required_cooling_power_kw` is currently only printed.)*

---

## 5. Files changed

| file | change |
|---|---|
| `common/config.py` | approach EVAP/COND/AIR; two flows (VENT 0.15, AC 0.62); damper / task-4 notes |
| `task1/flow_limits.py` | `ac_fan_flow_m3s`, `coil_outlet_T_AC`, `vent_step_landing_C`, `vent_overshoot_ok` |
| `task1/room.py` | `coil_outlet_B` (closure B, sat-table wet/dry + floor); RHS AC branch fixed-flow |
| `task1/simulation.py` | AC step uses `coil_outlet_B`; `ac_fan_undersized_steps` counter |
| `task2/cycle_opt.py` | Ex3-style inner COP optimisation (standard form + verification) |
| `main.py` | `fanU` column |

---

## 6. Simulation results (bore 30, Propane; clean model, fanU = 0)

| season | Tmin | Tmax | in-band | RHmin–max | AC start/min | VENT start/min | E_AC | E_vent | fanU |
|---|---|---|---|---|---|---|---|---|---|
| winter | 15.0 | 30.2 | 88 % | 11–60 % | 12 / 600 | 38 / 620 | 9.23 | 1.55 | 0 |
| spring | 15.0 | 34.4 | 83 % | 14–60 % | 19 / 745 | 30 / 530 | 11.78 | 1.32 | 0 |
| summer | 15.0 | 34.6 | 83 % | 22–60 % | 36 / 1065 | 6 / 30 | 17.88 | 0.07 | 0 |
| fall | 15.0 | 32.0 | 84 % | 18–60 % | 33 / 875 | 30 / 345 | 13.94 | 0.86 | 0 |

- **Humidity in band** (RH 11–60 % vs allowable 8–80 %); low-RH is ventilation-driven
  (cold dry ambient in winter), not the AC coil.
- **Energy now trustworthy** (no capped Q_cool).

---

## 7. Open issues / next

1. **Temperature overshoot (Tmax 30–34.6 °C > 27 band top)** — the dominant in-band
   killer. It is **control**, not the cycle/fan: `MIN_STANDSTILL` 10 min × slew
   `Q_server/(M·cp)` = 1.39 K/min ⇒ +13.9 K during lockout ⇒ ~35 °C.
   - Lever: reduce `MIN_STANDSTILL` (5 min ⇒ ~+7 K ⇒ ~28 °C). Trade-off: compressor
     short-cycling. Fully in-band needs a finer timestep.
2. **Thermal-mass uncertainty (report).** Overshoot magnitude is dominated by the
   **air-only** mass (215 kJ/K), spec'd minimal on purpose. A real room (racks,
   structure) has 10–100× more → far milder overshoot. Could flip "control is fragile".
3. **Cold-ambient over-delivery** — at cold ambient the AC delivers ~6.6 kW for ~1–2 kW
   of supplement → cycling. Inherent to bore-30 capacity rise + on/off (part-load story).
4. **Wire the `q_peak` screen** into bore selection (Task 3); then **re-tighten
   `AC_FAN_FLOW`** to the in-band max Q_AC once the overshoot is controlled.
