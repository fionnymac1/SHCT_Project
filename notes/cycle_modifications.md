# `cycle.py` — modifications (2026-06-22)

File: `src/task2/cycle.py`. Two changes, both **behavior-preserving** for the existing
outputs: change 1 is documentation, change 2 adds a new diagnostic field. The COP/capacity
shift you saw in the map did **not** come from here — it came from `config.py`
(`DELTA_T_SUBCOOL_K` 0.0 → `DT_APPROACH_COND_K`). These edits only document the model and
expose the discharge temperature.

---

## 1. Standard-form inner-optimization block (module docstring)

**Why:** the report rubric requires the inner COP optimization written in lecture-#3 standard
form (decision variables / objective / constraints). Previously the cycle was built at fixed
superheat and subcooling with no stated formulation. Added this block to the module docstring,
after the minimum-pressure-ratio paragraph:

```
Inner COP optimisation (lecture #3 standard form)
    decision variables : superheat dT_sh, subcooling dT_sc
                         (T_ev, T_co are fixed by the constant-approach assumption,
                          so they are NOT free decision variables in this model)
    objective          : maximise COP_inner = q_evap / w_comp
    constraints        : dT_sh >= dT_sh,min     (dry suction; compressor protection)
                         dT_sc <= T_co - T_amb  (sink bound; subcool only toward ambient)
                         p_co / p_ev >= 2       (compressor envelope; see clamp above)
                         T_dis <= T_dis,max     (discharge-temperature limit)
    solution           : the optimum lies on the constraint boundaries, so the map is
                         built at FIXED dT_sh, dT_sc (no per-point solver). Verified in
                         analysis/superheat_subcool_sweep.py:
                           dT_sc -> upper bound  T_co - T_amb : COP_inner is monotone
                             increasing in subcool for all three refrigerants
                             (+3.4..5.8 %). This is the dominant lever.
                           dT_sh -> lower bound  dT_sh,min    : COP_inner is nearly flat
                             and refrigerant-dependent in sign (Propane/R1234yf +, DME -),
                             so the dry-suction minimum is chosen; it is within ~1-3 % of
                             optimal for every fluid.
                         Both decisions are precomputed into the (T_room,T_amb) map
                         (Hint 1); the time simulation never re-optimises the cycle.
```

**Effect:** comments only — no change to any computed value.

---

## 2. Discharge-temperature output (`T_dis`)

**Why:** discharge temperature is the realistic *upper* constraint on superheat (it appears in
the optimization block above and in the `config.py` superheat justification). The cycle already
computed the actual discharge enthalpy `h2`; this just evaluates its temperature and returns it,
so the constraint can be monitored and the sweep script can report it.

Added one line in `cycle_point`, right after the discharge enthalpy is computed:

```python
    h1, h2s = z1["h"], z2s["h"]
    h2 = h1 + (h2s - h1) / eta_is
    T_dis = FCP.state(["p", "h"], [p_co, h2], refrigerant, Eh=EH)["T"]  # actual discharge temp
```

And `T_dis` was added to the returned dict:

```python
        "Q_AC_kW": Q_AC, "W_kW": W, "COP_inner": cop, "T_dis": T_dis,
        "T_AC": T_ev + config.DT_APPROACH_AIR_K,
```

**Effect:** one new key (`T_dis`, °C) in the `cycle_point` result; all existing keys
(`COP_inner`, `Q_AC_kW`, `m_dot`, …) are unchanged.

---

## Verification

- `cycle_point(15, 30, 30, "Propane")` runs clean; `T_dis` present; `COP_inner`/`Q_AC_kW`
  identical to before for the same inputs (the new field is purely additive).
- Discharge temps look physical (e.g. DimethylEther runs hottest, ~61→83 °C as superheat
  rises 0.5→20 K), consistent with `analysis/superheat_subcool_sweep.py` and its figure
  `superheat_subcool_sweep.png`.
- Run note: under the OneDrive mount, force a fresh compile before trusting bash runs —
  `find src -name "*.pyc" -delete; find src -name "*.py" -exec touch {} +` and
  `PYTHONDONTWRITEBYTECODE=1` (stale `.pyc` otherwise shadows edits).
