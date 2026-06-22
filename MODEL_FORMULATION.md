# Server-Room Cooling — Mathematical Formulation & Conventions

ETH SHCT SS2026. Reference for the code in `src/`. This documents **what the
code actually does today**, with conventions and symbols, and flags where the
code fixes a quantity that the task wants treated as a free variable. It is not
the report; it is the single source of truth for notation.

Faithful to: `common/config.py`, `task1/room.py`, `task1/control.py`,
`task1/simulation.py`, `task1/flow_limits.py`, `task2/cycle.py` (read 2026-06-22).

---

## 0. Units & sign conventions (one convention, no exceptions)

The course wrappers (`Fluid_CP`, `Fluid_CP_moist_air`, `Eh="CBar"`) and the
compressor module all use **engineering units**, and the whole model stays in
them. Raw CoolProp SI (Pa, K, J/kg) is never called directly.

| Quantity            | Symbol                | Unit         |
|---------------------|-----------------------|--------------|
| Temperature         | $T$                   | °C           |
| Temperature diff.   | $\Delta T$            | K            |
| Pressure            | $p$                   | bar          |
| Specific enthalpy (moist air, per kg **dry** air) | $h^*$ | kJ/kg$_a$ |
| Specific enthalpy (refrigerant) | $h$       | kJ/kg        |
| Humidity ratio      | $X = m_w/m_a$         | kg$_w$/kg$_a$ (dimensionless) |
| Power / heat rate   | $\dot Q,\ \dot W$     | kW           |
| Mass flow           | $\dot m$              | kg/s         |
| Time                | $t$                   | s (step in min) |
| Air mass in room    | $M_a$                 | kg dry air   |

Sign convention: $\dot Q_\text{cool} > 0$ removes heat from the room. Relative
humidity $\phi \in [0,1]$. All states at $p = 1$ bar (room side).

---

## 1. Room model (0-D, quasi-steady) — `room.py`

Interior $10\times 6\times 3 = 180\ \mathrm{m^3}$. Constant dry-air mass

$$M_a = \rho_a V = 1.19 \times 180 = 214.2\ \mathrm{kg}\quad(\text{brief: } \approx 216).$$

State per the Exercise-11 convention: $\;z = [\,h^*,\ m_w\,]$ with $X = m_w/M_a$.

**Energy balance** (kW):
$$M_a\,\frac{dh^*}{dt} = \dot Q_\text{server}(t) - \dot Q_\text{cool}.$$

**Water balance** (kg/s):
$$\frac{dm_w}{dt} = \big(X_\text{sink} - X\big)\,\dot m,$$

where $(X_\text{sink}, \dot m)$ depend on the active mode (§3). Humidity is
**monitored, not controlled** — there is no (de)humidifier actuator; $X$ moves
only through the AC coil (condensation) and through VENT air exchange.

**Inversion** $(h^*, m_w)\to(T,\phi,X)$ is a Newton solve on the module's own
forward $h^*(T,X)$ (not CoolProp's `["h*","X"]` inversion, which crashes once
the AC dries the room below the 0.01 °C triple-point dew line). See `room.invert`.

---

## 2. Initial & boundary conditions

| Symbol | Meaning | Value | Source |
|--------|---------|-------|--------|
| $T_0$ | initial room temp | 15 °C | brief |
| $\phi_0$ | initial RH | 0.60 | brief |
| $\dot Q_\text{server}(t)$ | server load | from `server_heating_power.txt`, 48 pts/day, 30-min sampling, periodic | data |
| $T_\text{amb}(t)$ | ambient temp | per season file, 48 pts/day | data |
| $\phi_\text{amb}$ | ambient RH | 0.60 | brief |
| band | acceptable $T$ | $[18, 27]$ °C (ASHRAE TC9.9 recommended) | assumption |
| $\phi$ allowable | monitored | $[0.08, 0.80]$ | ASHRAE A1 |

Time grid: $\Delta t = 5$ min (`TIME_STEP_MIN`). ODE integrated with
`scipy.odeint` over each step; cooling rate re-evaluated at the **current** room
enthalpy each step, so it self-limits as the room approaches the sink.

---

## 3. The three modes (mutually exclusive — one shared fan) — `room.py::rhs`

Both actuators are **strictly ON/OFF, full capacity when on**. There is **no
capacity modulation**. This is the crux of your two questions — see the DOF
table in §8.

### OFF
$$\dot Q_\text{cool} = 0, \qquad \frac{dm_w}{dt} = 0.$$

### VENT (free cooling — ambient air pushed through)
Air mass flow is **fixed** at the single design flow:
$$\dot m = \rho_a\,\dot V_\text{design}, \qquad \dot V_\text{design} = 0.30\ \mathrm{m^3/s}\ \Rightarrow\ \dot m = 0.357\ \mathrm{kg/s}.$$
$$\dot Q_\text{cool} = \dot m\,\big(h^* - h^*_\text{amb}\big)\ \ (\ge 0),\qquad
X_\text{sink} = X_\text{amb}.$$
Cooling power floats only because $h^*-h^*_\text{amb}$ shrinks as the room cools;
**$\dot m$ does not change**. $\dot Q_\text{cool}\to 0$ as $T_\text{room}\to T_\text{amb}$.

### AC (recirculation through the VCC coil)
Cooling power is **fixed** at the full compressor capacity from the map (§5):
$$\dot Q_\text{cool} = \dot Q_\text{AC}(T_\text{room}, T_\text{amb}),$$
and the **air-side recirculation flow is back-solved** (it is a *consequence*,
not a control input):
$$\dot m = \frac{\dot Q_\text{AC}}{\,h^* - h^*_\text{sink}\,}.$$
Coil air-outlet state (dehumidification two-case):
$$T_\text{AC} = T_\text{ev} + \Delta T_\text{app,air} = T_\text{room} - \Delta T_\text{app,ev} + \Delta T_\text{app,air} = T_\text{room} - 12 + 3 = T_\text{room} - 9,$$
$$X_\text{sink} = \min\!\big(X,\ X_\text{sat}(T_\text{AC})\big), \qquad
h^*_\text{sink} = h^*\big(T_\text{AC}, X_\text{sink}\big).$$
If $X > X_\text{sat}(T_\text{AC})$ the coil condenses water ⇒ room dries; else
the process is purely sensible.

> **Key point.** $T_\text{AC}$ is **slaved to $T_\text{room}$** through two fixed
> config constants ($\Delta T_\text{app,ev}=12$, $\Delta T_\text{app,air}=3$). It
> is not a free variable in the current code. As $T_\text{room}$ drifts up during
> an AC-off excursion, $T_\text{AC}$ follows it up — the coil "tracks" the room.

---

## 4. Control state machine — `control.py`

On/off with hysteresis on **temperature only** (humidity has no actuator).
Setpoints centred in the band:

$$T_\text{ON} = 23.5\ \text{°C}\ (\text{cool ON at/above}),\qquad
T_\text{OFF} = 21.5\ \text{°C}\ (\text{cool OFF at/below}),$$

so a 2 K deadband around a ~22.5 °C target. Inside the deadband the current mode
is held.

**Mode selection logic** (`decide`):
- `want_cool` $\equiv T_\text{room} \ge T_\text{ON}$; `want_off` $\equiv T_\text{room} \le T_\text{OFF}$.
- Free-cooling-first: if cooling is wanted and VENT can carry the **full** load at the design flow → VENT; else AC.
- Vent-assist: while the compressor is locked in standstill, if ambient $< T_\text{room}$ the idle shared fan runs VENT for *partial* cooling (never over-cools, since this branch is only reached when the design flow cannot carry the full load).
- AC and VENT are never simultaneous (one fan).

**Feasibility tests:**
$$\text{vent\_available}:\ T_\text{amb} < T_\text{room} - 0.5,$$
$$\text{vent\_feasible}:\ \text{vent\_available} \ \wedge\ \dot V_\text{min}(\dot Q_\text{demand}, T_\text{room}-T_\text{amb}) \le \dot V_\text{design}.$$

**Timing constraints (compressor only):**
$$n_\text{run} \ge N_\text{run} = \lceil 5/\Delta t_\text{min}\rceil = 1\ \text{step},\qquad
n_\text{idle} \ge N_\text{stand} = \lceil 10/\Delta t_\text{min}\rceil = 2\ \text{steps}.$$
These gate **AC** transitions only; the fan (VENT/OFF) switches freely. The
standstill clock counts time since the compressor last ran, including any
intervening VENT.

---

## 5. AC cycle — subcritical VCC — `cycle.py` (Task-2 stand-in)

Constant approach temperatures (held off-design too):
$$T_\text{ev} = T_\text{room} - \Delta T_\text{app,ev},\qquad
T_\text{co} = T_\text{amb} + \Delta T_\text{app,co},\qquad
\Delta T_\text{app,ev}=12,\ \Delta T_\text{app,co}=5.$$

Saturation pressures $p_\text{ev}=p_\text{sat}(T_\text{ev})$, $p_\text{co}=p_\text{sat}(T_\text{co})$.

**Minimum-pressure-ratio envelope** (binds at low ambient):
$$\text{if } \frac{p_\text{co}}{p_\text{ev}} < \Pi_\text{min}=2:\quad
p_\text{co} \leftarrow \Pi_\text{min}\,p_\text{ev},\ \ T_\text{co}\leftarrow T_\text{sat}(p_\text{co}).$$

**State points** (refrigerant; $Eh=$ "CBar"):
$$\begin{aligned}
1&:\ \text{superheated suction at } (T_\text{ev}+\Delta T_\text{sh},\ p_\text{ev}),\quad \Delta T_\text{sh}=5\ \text{K}\\
2s&:\ \text{isentropic to } p_\text{co};\quad h_2 = h_1 + (h_{2s}-h_1)/\eta_\text{is}\\
3&:\ \text{sat. liquid at } T_\text{co}\ (\text{minus } \Delta T_\text{sc});\quad \Delta T_\text{sc}=0\\
4&:\ \text{isenthalpic expansion},\ h_4 = h_3.
\end{aligned}$$

**Performance:**
$$q_\text{evap} = h_1 - h_4,\quad w_\text{comp} = h_2 - h_1,\quad
\mathrm{COP_{inner}} = \frac{q_\text{evap}}{w_\text{comp}},\quad
\dot Q_\text{AC} = \dot m_\text{ref}\, q_\text{evap}.$$

$\eta_\text{is}$ and $\dot m_\text{ref}$ come from
`recip_comp_corr_SP((T_ev, T_co, ΔT_sh, ΔT_sc, D), refrigerant)` — note the
function **ignores** $\Delta T_\text{sc}$ for $\dot m$ and $\eta_\text{is}$.
Capacity scales $\propto D^2$ (bore); COP is independent of bore.

**Precompute (Hint 1):** the cycle is **not** re-solved every timestep.
$\dot Q_\text{AC}$ and $\mathrm{COP_{inner}}$ are built on a $(T_\text{room},
T_\text{amb})$ grid (`build_map`) and interpolated (`lookup`,
`RegularGridInterpolator`). Grid: $T_\text{room}\in[13,36]$ step 1,
$T_\text{amb}\in[0,40]$ step 2.

---

## 6. Part-load degradation (Hint 2) — `simulation.py::cop_res`

Under on/off the compressor delivers full $\dot Q_\text{AC}$ whenever it runs, so
the part-load ratio is the **time-averaged duty**, keyed to demand/capacity:
$$\mathrm{PLR} = \min\!\Big(\frac{\dot Q_\text{server}}{\dot Q_\text{AC}},\,1\Big),
\qquad
\mathrm{COP_{res}} = \mathrm{COP_{inner}}\,\frac{\mathrm{PLR}}{0.9\,\mathrm{PLR}+0.1}.$$
Electrical draw while AC is on: $\dot W_\text{el} = \dot Q_\text{AC}/\mathrm{COP_{res}}$.
Oversizing ($\dot Q_\text{AC}\gg\dot Q_\text{server}$ ⇒ small PLR) makes the
$0.9\,\mathrm{PLR}+0.1$ denominator bite — this is the **bore/refrigerant lever**
for Task 3. (Keying PLR to $\dot Q_\text{cool}/\dot Q_\text{AC}$ would give 1.0 and
silently delete the penalty.)

---

## 7. Flow limits — `flow_limits.py`

Sensible minimum flow to carry load $\dot Q$ at difference $\Delta T$:
$$\dot V_\text{min} = \frac{\dot Q}{\rho_a\,c_{p,a}\,\Delta T},\qquad
c_{p,a}=1.006\ \mathrm{kJ/kgK}.$$
For VENT $\Delta T = T_\text{room}-T_\text{amb}$; for AC $\Delta T = T_\text{room}-T_\text{AC}$.

**Acoustic cap (upper bound only):** Beaufort-5 face velocity × supply area,
$$\dot V_\text{max} = v_\text{B5}\,A_\text{supply} = 10.7 \times 0.20 = 2.14\ \mathrm{m^3/s}.$$
The **operating** flow is the design value $\dot V_\text{design}=0.30\ \mathrm{m^3/s}$
(≈14 % of cap), sized so one VENT step cannot overshoot the lower band: with room
time constant $\tau = M_a/(\rho_a \dot V_\text{design})$, the worst step closes
$f = 1-e^{-\Delta t/\tau}$ of $(T_\text{room}-T_\text{amb})$.

Mode-switch threshold (where $\dot V_\text{min}=\dot V_\text{max}$):
$\Delta T_\text{switch} = \dot Q/(\rho_a c_{p,a}\dot V_\text{max})$.

---

## 8. Degrees of freedom — direct answers to the two questions

| Quantity | In the code it is… | A control DOF? | A design / optimisation DOF? |
|---|---|---|---|
| Mode $\in\{$OFF,VENT,AC$\}$ | the **only** thing the controller sets | **Yes** (bang-bang, hysteresis) | — |
| $\dot m_\text{air}$, VENT | **fixed** at $\rho_a\dot V_\text{design}=0.357$ kg/s | **No** | Yes — $\dot V_\text{design}$ chosen once (sizing) |
| $\dot m_\text{air}$, AC | **back-solved** $=\dot Q_\text{AC}/(h^*-h^*_\text{sink})$ | **No** (passive consequence of fixing $\dot Q_\text{AC}$) | No |
| $T_\text{AC}$ | **slaved** $=T_\text{room}-9$ via fixed approaches | **No** | Yes *in principle* — see below |
| $\dot Q_\text{AC}$ | full capacity from $(T_\text{room},T_\text{amb})$ map | **No** (full-blast when on) | Yes — via bore $D$ (Task 3) |
| $\Delta T_\text{sh},\Delta T_\text{sc}$ | **fixed** at 5 K / 0 K defaults | No | **Yes (Task-2 inner opt — currently NOT exercised)** |

**Q1 — Are we varying $\dot m$ of air to achieve the desired $T_\text{room}$?**
**No.** $T_\text{room}$ is regulated purely by **duty cycle** (on/off mode
switching). In VENT, $\dot m$ is pinned at the single design flow. In AC, $\dot m$
"floats" but only as a passive back-calculation to keep the energy balance
consistent with a *fixed* $\dot Q_\text{AC}$ — it is bookkeeping, not a manipulated
variable. Per the task spec (strictly on/off), modulating $\dot m$ at runtime
would be out of scope; the legitimate lever is the **design-time** choice of
$\dot V_\text{design}$.

**Q2 — Can we vary $T_\text{AC}$?**
Not at runtime, and not currently at all. $T_\text{AC}=T_\text{room}-9$ is fixed
by two config constants ($\Delta T_\text{app,ev}$, $\Delta T_\text{app,air}$). You
*can* make it variable, but it belongs to the **Task-2 cycle optimisation**, not
to the Task-1 controller: choose the cycle's free variable(s) (superheat/
subcooling, or the evaporator approach) to **maximise $\mathrm{COP_{inner}}$ at
each operating point**, subject to constraints. The hooks already exist —
`cycle_point(..., dt_sh, dt_sc)` accepts them — but `build_map` calls it with the
defaults, so **the inner optimisation is not implemented yet** (see §10).

---

## 9. Optimisation in standard form (lecture #3) — the target for the report

**Inner (cycle), per $(T_\text{room},T_\text{amb})$, per $(D,\text{refrigerant})$:**
- **Degrees of freedom:** $\Delta T_\text{sh}\ (\ge \Delta T_\text{sh,min})$, optionally $\Delta T_\text{sc}$, optionally $\Delta T_\text{app,ev}$.
- **Objective:** $\max\ \mathrm{COP_{inner}}$.
- **Constraints:** $p_\text{co}/p_\text{ev}\ge \Pi_\text{min}=2$; subcritical $p_\text{co}<p_\text{crit}$; dry compression (suction superheated); if dehumidification required, $T_\text{AC}\le$ room dew point ($\approx 7.3$ °C at 15 °C/60 %); $\dot Q_\text{AC}\ge \dot Q_\text{server,peak}$ at the hottest ambient (sizing screen).

> **Status: the code currently fixes the DOF instead of optimising them.**
> $\Delta T_\text{sh}=5$, $\Delta T_\text{sc}=0$, $\Delta T_\text{app,ev}=12$ are
> constants. To satisfy the rubric you must either (a) actually run this inner
> optimisation in `build_map`, or (b) justify the fixed values as a deliberate,
> defensible operating choice and say so explicitly.

**Outer (selection, Task 3):** over $D\in\{30,40,50\}$ mm and refrigerant
$\in\{$Propane, R1234yf, DimethylEther$\}$, choose the combination trading off
total electrical energy, number of AC start/stops, operating times, and room-air
condition (temperature **and** humidity).

---

## 10. Open gaps / flags (own these before submission)

1. **Inner COP optimisation not implemented.** $\Delta T_\text{sh},\Delta T_\text{sc}$ are plumbed through `cycle_point` but never swept; `build_map` uses defaults. Against the explicit rubric ("optimisation in standard form"). Decide: optimise, or justify-and-declare.
2. **No proportional action in AC.** $\dot Q_\text{cool}=\dot Q_\text{AC}$ is full-blast whenever on, independent of how far $T_\text{room}$ is above setpoint. Control quality therefore rests entirely on duty cycle + sizing; if $\dot Q_\text{AC}\gg\dot Q_\text{server}$ each on-step slews the room hard and the min-standstill lockout then lets it overshoot up. This (not the hysteresis width) is the documented overshoot mechanism; the mitigation is sizing $\dot Q_\text{AC}$ near peak load (small bore).
3. **Fan power omitted in AC mode.** `simulation.py` counts only compressor electrical draw in AC; the shared ventilator also pushes air over the evaporator. If the same fan serves AC recirculation, its power should be in the AC energy tally (coupling constraint, §1 of the brief).
4. **AC recirculation $\dot m$ is unbounded.** $\dot m=\dot Q_\text{AC}/(h^*-h^*_\text{sink})$ has only a $\text{denom}>10^{-6}$ guard; it is never checked against what the single shared fan can actually deliver. The "one ventilator serves both modes" coupling is not enforced on the AC side.
5. **$T_\text{AC}$ tracks $T_\text{room}$.** Because approaches are constant, the coil outlet rises with the room during an excursion — physically reasonable for a constant-approach model, but state it; it weakens dehumidification exactly when the room is hottest.

---

*Symbols not redefined here follow the course wrappers. Keep this file in sync
with `config.py` — every numeric constant above is mirrored there.*
