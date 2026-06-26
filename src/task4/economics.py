"""
Task 4 - electricity cost of the AC and ventilation system.

Builds on Task 3's per-season energy totals (results/task3_energy_by_season.csv,
written by main_task3.py via task3.sweep.save_energy_by_season -- one E_ac_kWh /
E_vent_kWh per (refrigerant, bore, season), i.e. per representative day). Two
assumptions this task is responsible for owning (both previously flagged as
placeholders, see notes/Compressor_Model_Bridge.md point P7 and notes/NOTES_Task1.md):

  1. Electricity tariff (config.ELEC_PRICE_CHF_PER_KWH), ONE PER SEASON -- the
     task sheet gives no number or region; sourced separately per representative
     day and owned as an assumption in the report.
  2. Compressor motor + drive efficiency (config.ETA_MOTOR_ELEC): the compressor
     model (recip_comp_corr_SP) returns FLUID/shaft power, not the electrical
     power actually billed. simulate_season's E_ac_kWh is fluid energy; this
     module converts it to billed electrical energy via
         E_ac_elec = E_ac_fluid / ETA_MOTOR_ELEC.
     The ventilation fan's E_vent_kWh is already an electrical-power stand-in
     (FAN_SPECIFIC_POWER_KW_PER_M3S in task1.simulation), so it is NOT divided
     by ETA_MOTOR_ELEC.

Each representative day stands for one season (~1/4 of the year); annual
energy/cost scales each season's one-day total by
config.DAYS_PER_REPRESENTATIVE_SEASON.
"""
import pandas as pd
from common import config


def season_cost(season, E_ac_fluid_kWh, E_vent_elec_kWh, price_by_season=None):
    """One representative day's AC + ventilation energy -> that season's
    annualised electrical cost. Returns a dict (energy + cost, AC/vent/total)."""
    price_by_season = config.ELEC_PRICE_CHF_PER_KWH if price_by_season is None else price_by_season
    price = price_by_season[season]
    n_days = config.DAYS_PER_REPRESENTATIVE_SEASON

    E_ac_elec_day = E_ac_fluid_kWh / config.ETA_MOTOR_ELEC
    E_ac_year = E_ac_elec_day * n_days
    E_vent_year = E_vent_elec_kWh * n_days

    return {
        "season": season,
        "E_ac_year_kWh": E_ac_year, "E_vent_year_kWh": E_vent_year,
        "E_total_year_kWh": E_ac_year + E_vent_year,
        "cost_ac_CHF_year": E_ac_year * price,
        "cost_vent_CHF_year": E_vent_year * price,
        "cost_total_CHF_year": (E_ac_year + E_vent_year) * price,
    }


def load_energy_by_season(path=None):
    """Read the per-season energy table main_task3.py writes (Task 4 input).
    Raises FileNotFoundError with a clear pointer if Task 3 hasn't been (re)run
    since task3.sweep.save_energy_by_season was added."""
    path = path or "results/task3_energy_by_season.csv"
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        raise FileNotFoundError(
            "%s not found -- run 'python src/main_task3.py' (it now also writes "
            "this per-season breakdown alongside the design-comparison table)." % path)


def design_economics(df_energy, price_by_season=None):
    """df_energy: the long-form (refrigerant, bore_mm, season, E_ac_kWh,
    E_vent_kWh) table from load_energy_by_season(). Returns one row per
    (refrigerant, bore_mm) design with the full-year electrical cost breakdown,
    summed across all four representative seasons."""
    rows = []
    for (refrigerant, bore_mm), g in df_energy.groupby(["refrigerant", "bore_mm"]):
        per_season = [season_cost(r["season"], r["E_ac_kWh"], r["E_vent_kWh"], price_by_season)
                      for _, r in g.iterrows()]
        totals = pd.DataFrame(per_season).drop(columns="season").sum().to_dict()
        rows.append({"refrigerant": refrigerant, "bore_mm": bore_mm, **totals})
    return pd.DataFrame(rows)
