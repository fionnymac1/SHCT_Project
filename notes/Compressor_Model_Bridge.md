# Compressor Model — Course ↔ Project Bridge

Source review: Lecture 6 (`SHCT26_Lec6.pdf`), Exercise 6 (task + both solution
notebooks + slides), project task (`StudentProject_task.pdf`), our `compressor_model.py`
+ `cycle.py`. All capacity/COP numbers below were produced by **running the provided
`recip_comp_corr_SP` correlation** at `T_room = 15 °C` (verified, not estimated).

---

## TL;DR — the part you were missing

The course compressor model is **one function that returns two efficiencies**,
`η_is` and `η_vol`, as functions of the operating point. Everything else you build
around it. In particular:

- **Mass flow is not free.** `ṁ = η_vol · ρ_suction · V̇_theo`, where
  `V̇_theo = V_cyl · f_mech · n_cyl` is **fixed geometry**. The bore `D` sets
  `V_cyl ∝ D²`, so **cooling capacity scales as D²** (and linearly with cylinder count).
- The project's `recip_comp_SP` just folds `ṁ = η_vol·ρ·V̇_theo` *inside* the function
  and returns `(η_is, ṁ)` directly. You hand it `(T_ev, T_co, ΔT_sh, ΔT_sc, D)`.

**So "what's wrong with our model" is not really the compressor maths — it's three
sizing/coupling issues that the compressor sits at the centre of:**

1. **Capacity is set by bore × cylinder count, and the cylinder count is contradictory**
   (task text says 4, the provided code computes 2). This is a clean ×2 on Q_AC and it
   *flips which bore is the right choice.*
2. **The 5-min timestep is too coarse to hold a tight band by on/off** — independent of
   the compressor. This is what actually forced the modulating-control workaround.
3. **We have not yet done the "COP-optimal at each timestep" inner optimisation** — the
   one genuine cycle DOF (superheat, and a bounded subcooling) is currently fixed.

Detail below.

---

## 1. What Lecture 6 / Exercise 6 actually cover

**Lecture 6** is the compressor lecture. Relevant content:

- **Isentropic efficiency** — referenced to an *isentropic* compression at the same
  pressure ratio:  `η_is = (h2s − h1)/(h2 − h1) = P_isentropic / P_fluid`.
  Used to get the real outlet:  `h2 = h1 + (h2s − h1)/η_is`. (Our `cycle.py` does exactly this.)
- **The efficiency chain** — what you actually pay for is electrical:
  `P_elec = P_fluid + losses(chamber, mech, elec)`, i.e.
  `η_global = P_isentropic/P_elec = η_elec · η_mech · η_is`.
  The course's working simplification is `P_elec ≈ P_fluid` (mechanical/electrical
  losses neglected). **This matters for Task 4 cost** — see §5.
- **Volumetric efficiency** — `η_vol = V̇_real/V̇_theo = ṁ_real/ṁ_theo`, with
  `V̇_theo = V_cyl · f_mech · n_cyl` and `ṁ_theo = ρ_in · V̇_theo`.
- **Positive-displacement vs dynamic** compressors; the **reciprocating piston** as the
  worked example; and the **operating envelope** (the limits a real compressor must stay
  inside).

**Exercise 6** builds the envelope of a *fixed* compressor (GEA-Bock HG-HC-12P:
`n_cyl = 2`, bore/stroke 34/34 mm, `V̇_theo = 5.4 m³/h`). The model is
`Compressor_model_CP.getETA(T_in, p_in, p_out, fluid) → [η_is, η_vol]`. The exercise then:
1. plots `η_is`, `η_vol` vs pressure ratio (η_is rises to a ~0.6 plateau; η_vol falls
   with pressure ratio → so does ṁ);
2. maps the **envelope** over (T_ev, T_co), flagging *why* each infeasible point is out:
   `P_el > P_el,max` (1.2 kW), `T_discharge > T_out,max` (100 °C), or `T_ev > T_co`.

Take-away: in the course, **η_is and η_vol are the model; capacity, power and feasibility
are things you compute from them.**

---

## 2. The two compressor functions, side by side

| | Exercise 6 `getETA` | Project `recip_comp_SP` (file: `recip_comp_corr_SP`) |
|---|---|---|
| Inputs | `T_in, p_in, p_out, fluid` | `(T_ev, T_co, ΔT_sh, ΔT_sc, D), fluid` |
| Returns | `η_is, η_vol` | `η_is, ṁ` |
| Mass flow | you compute `ṁ = η_vol·ρ·V̇_theo` | done **inside** the function |
| Geometry | fixed (34/34 mm, 2-cyl, 5.4 m³/h) | reference 50 mm / 39.3 mm, **2-cyl**, f_el≈48.5 Hz, then scaled by `(D/50)²` |
| Units | `CKPa` (°C, kPa) | `CBar` (°C, bar) internally |

The project function's correlations (verbatim):

```
η_vol = 1 − 0.08244·(pr − 1)^0.72773
η_is  = 0.66981 − 0.6/(pr − 0.01466)^(0.00838·p_suc[kPa]) − 0.00102·pr^1.8
ṁ     = (1/v_suc)·η_vol·[(π/4)·D²·H]·f_mech·n_cyl ,  with D=50mm,H=39.3mm,n_cyl=2 baked in,
        then × (D/50mm)²
pr    = p_co / p_ev
```

It is the **same physics as Exercise 6**, repackaged so the bore is a knob.

---

## 3. How bore and refrigerant enter (bridge to Tasks 2–3)

- **Bore D** enters only through `V̇_theo ∝ D²` → `ṁ ∝ D²` → `Q_AC ∝ D²`. It does *not*
  change η_is, η_vol, or COP at a given (T_ev, T_co). **Bore is a pure capacity knob.**
- **Refrigerant** enters through every Fluid_CP state (ρ_suc, h's, and the saturation
  pressures that set `pr`). It changes both capacity *and* COP.
- **Min pressure ratio ≥ 2** — the project replaces Ex.6's full envelope with this single
  constraint ("To maintain the compressor's operating envelope, consider a minimum
  pressure ratio of 2"). So our cycle's min-ratio clamp is the *whole* required envelope
  check — we are **not** missing the P_el/T_out checks (they're not asked for here,
  though the data is there if we want a sanity plot).

---

## 4. What we've built — and the real numbers

`cycle.py` implements the subcritical VCC exactly as the course does (states via
`Fluid_CP`, `h2` via η_is, refrigerating effect `q = h1 − h4`, `COP = q/w`), calls the
provided function for `(η_is, ṁ)`, applies the min-pr≥2 clamp, and precomputes
`Q_AC`/`COP` on a (T_room, T_amb) grid for interpolation (Hint 1). That part is sound and
faithful to the course.

**Capacity & COP, as the code currently runs (2-cylinder, Propane, T_room = 15 °C):**

| Bore | Q_AC summer (Tamb 32) | Q_AC mild (Tamb≤~18, clamped) | COP_inner | ΔT per 5-min step when ON* |
|---|---|---|---|---|
| 30 mm | 3.8 kW | 4.3 kW | 4.4 / 6.0 | **+1.0 … +1.6 K (cannot meet 5 kW peak)** |
| 40 mm | 6.8 kW | 7.6 kW | 4.4 / 6.0 | −2.5 … −3.6 K |
| 50 mm | 10.6 kW | 11.8 kW | 4.4 / 6.0 | −7.8 … −9.5 K (large undershoot) |

\* `ΔT = (Q_server − Q_AC)·Δt/C`, with peak `Q_server = 5 kW`, `C = 215 kJ/K`, `Δt = 300 s`.
Demand to beat = **5 kW peak**.

**If the compressor is actually 4-cylinder (task text), double every Q_AC:** 30 mm → ~8 kW
(right-sized), 40 mm → ~14 kW (~3× oversized), 50 mm → ~21 kW (~4× oversized).

Refrigerant shifts capacity ~30 %: at 2-cyl/40 mm, summer Q_AC is 6.8 kW (Propane) but
only ~4.8 kW (R1234yf) and ~4.7 kW (DME) — i.e. **with R1234yf/DME the 40 mm bore barely
meets peak at 2-cyl.** Discharge temps stay 38–69 °C (DME hottest), all well under 100 °C.

---

## 5. Problems & open questions

**P1 — Cylinder count: 4 (task) vs 2 (code). [ask Lana/Philip]**
`StudentProject_task.pdf`: *"a 4-cylinder reciprocating compressor… D = {30,40,50} mm."*
The provided `recip_comp_corr_SP` computes `ṁ` for **2 cylinders** (the `·48.55/2·2`
term, German comment *"Der Verdichter hat zwei Zylinder"*). Our `cycle.py` uses the
function as-is → **2-cyl**; `config.COMPRESSOR_N_CYL = 4` is set but **never applied.**
This is a clean ×2 on capacity and it *flips the selection*: at 2-cyl the sweet spot is
~40 mm (30 mm can't meet peak); at 4-cyl the sweet spot is ~30 mm (40/50 mm wildly
oversized). **Resolve before any sizing/selection.** Options: trust the code (2-cyl) or
multiply ṁ by 2 (4-cyl). Needs a one-line answer from the staff.

**P2 — The real cause of the control problem is the timestep, not (only) the compressor.**
Servers alone, AC off: **+6.96 K per 5-min step** at 5 kW. That single number exceeds the
2 K hysteresis (15.5/17.5) *and* the 3 K band (15–18) — so **bang-bang at a 5-min step
cannot hold the band regardless of compressor size**; the room blows past the top every
off-cycle. That is what forced the switch to modulating control, which in turn made the
Task-3 "start/stop count" criterion meaningless. The compressor adds a *second* problem
on the cold side (oversized bore/4-cyl → −8 to −20 K undershoot per step), but the
timestep is the first-order issue. **Fixes:** sub-step the controller (≤~1–2 min) or run
the timestep sensitivity (already a TODO); *then* right-size the bore so on/off cycles
cleanly. (Correction to my earlier claim: the "−12 K/step" figure was the **4-cyl, 40 mm**
case; as the code runs now, 40 mm gives only −2.5…−3.6 K/step.)

**P3 — Part-load penalty quantifies the oversizing cost (Hint 2).**
`COP_res = COP_inner · PLR/(0.9·PLR + 0.1)`, `PLR = Q_demand/Q_AC`. A right-sized unit
(40 mm 2-cyl, PLR≈0.7) keeps ~96 % of COP; a 4× unit (50 mm 4-cyl) at low night load
(PLR≈0.1) keeps **~50 %**. So oversizing is penalised twice — control chatter *and*
efficiency. This should be the spine of the Task-3 argument.

**P4 — The "COP-optimal at each timestep" inner optimisation is not done yet.**
We currently fix `ΔT_sh = 5 K`, `ΔT_sc = 0`. The genuine free DOF in `recip_comp_SP` is
**superheat** (it moves ρ_suc, η_vol, ṁ, and the suction enthalpy). Subcooling also
raises `q_evap` — but note the function **ignores ΔT_sc for ṁ/η**, so in this model more
subcooling is a "free" COP gain and must be **bounded by physics** (you cannot subcool
below sink temperature ≈ T_amb + approach). Task 2 = write this as a standard
optimisation (DOF = ΔT_sh, bounded ΔT_sc; objective = max COP; constraints = pr ≥ 2,
ΔT_sh > 0, ΔT_sc ≤ subcooling-available) and precompute on the grid (Hint 1).

**P5 — RICM60S is the *ventilator*, not the compressor. [corrects a prior assumption]**
`RICM60S specifications.pdf` is a **side-channel blower (Seitenkanalverdichter, Rico)** —
an air mover with mbar pressure rise and Q in m³/h, plotted as fan curves. It is **not**
the refrigerant compressor and tells us nothing about cylinder count (P1 cannot be
resolved from it). It *is* plausibly the project's ventilator → use its curve for **fan
power (Task 4)** instead of the 1.0 kW·s/m³ placeholder. ⚠️ Its max flow looks ~150–250
m³/h (~0.05 m³/s), which is ~40× **below** our assumed V̇_max = 2.14 m³/s — if this
blower is the intended fan, the fan (not duct velocity) limits ventilation and our
Task-1.2 flow assumption is far too high. Worth confirming.

**P6 — Min-pr clamp makes AC performance ambient-independent below the clamp.**
Once `p_co` is clamped to `2·p_ev`, the cycle (hence Q_AC, COP) is identical for *all*
ambients cold enough to clamp — that's why "mild 20 °C" and "winter 2 °C" give identical
rows above. Physically defensible (compressor holds minimum head) but worth a sentence in
Uncertainties; it means AC behaviour in spring/fall/winter is flat, set by the clamp not
the weather.

**P7 — Minor: function name + electrical power.**
(a) Task PDF calls it `recip_comp_SP`; the provided file defines `recip_comp_corr_SP`.
We use the latter (works); confirm there isn't a second canonical function on Moodle.
(b) Our `W = ṁ·(h2 − h1)` is fluid/inner power. True electrical power (for cost) is
`P_elec = P_fluid/(η_mech·η_elec)`, which the function does not give → we implicitly assume
`η_mech·η_elec ≈ 1` (the Ex.6 simplification). State this in Task 4.
