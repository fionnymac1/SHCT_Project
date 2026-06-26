"""
Task 4 - electricity cost of the AC and ventilation system.

Builds on Task 3's per-hour energy table (results/task3_energy_by_hour.csv,
written by main_task3.py via task3.sweep.save_energy_by_hour -- E_ac_kWh /
E_vent_kWh per (refrigerant, bore, season, hour-of-day)) and REAL day-ahead
electricity prices (common.data_io.load_dayahead_prices -- one real calendar
day per representative season, ENTSO-E Swiss bidding zone, hourly). Each
hour's energy is costed at that hour's actual price, not a flat assumed rate.

Two assumptions this task is responsible for owning (both previously flagged
as placeholders, see notes/Compressor_Model_Bridge.md point P7 and
notes/NOTES_Task1.md):

  1. Electricity tariff: REAL hourly day-ahead prices (config.FILE_DAYAHEAD_
     PRICES), converted EUR/MWh -> CHF/kWh via config.EUR_TO_CHF.
  2. Compressor motor + drive efficiency (config.ETA_MOTOR_ELEC): the
     compressor model (recip_comp_corr_SP) returns FLUID/shaft power, not the
     electrical power actually billed. simulate_season's E_ac_kWh is fluid
     energy; this module converts it to billed electrical energy via
         E_ac_elec = E_ac_fluid / ETA_MOTOR_ELEC.
     The ventilation fan's E_vent_kWh is already an electrical-power stand-in
     (FAN_SPECIFIC_POWER_KW_PER_M3S in task1.simulation), so it is NOT divided
     by ETA_MOTOR_ELEC.

NOT annualised: each representative day's real day-ahead price is specific to
that one calendar date and does not represent ~91 days of the season the way
the weather data is assumed to (prices swing day-to-day for unrelated market
reasons). Costs reported here are therefore for the four representative days
only, matching how Task 3 already reports E_total_kWh ("kWh / 4 days"),
not a year.
"""
import pandas as pd
from common import config, data_io


def load_energy_by_hour(path=None):
    """Read the per-hour energy table main_task3.py writes (Task 4 input).
    Raises FileNotFoundError with a clear pointer if Task 3 hasn't been (re)run
    since task3.sweep.save_energy_by_hour was added."""
    path = path or "results/task3_energy_by_hour.csv"
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        raise FileNotFoundError(
            "%s not found -- run 'python src/main_task3.py' (it now also writes "
            "this per-hour breakdown alongside the design-comparison table)." % path)


def design_economics(df_energy, prices_by_season=None):
    """df_energy: the long-form (refrigerant, bore_mm, season, hour, E_ac_kWh,
    E_vent_kWh) table from load_energy_by_hour(). prices_by_season defaults to
    data_io.load_dayahead_prices() (real hourly CHF/kWh per season + the
    calendar date it came from). Returns one row per (refrigerant, bore_mm)
    design with the cost over the four representative days, AC/vent split."""
    prices_by_season = data_io.load_dayahead_prices() if prices_by_season is None else prices_by_season

    rows = []
    for (refrigerant, bore_mm), g in df_energy.groupby(["refrigerant", "bore_mm"]):
        cost_ac = cost_vent = E_ac = E_vent = 0.0
        for _, r in g.iterrows():
            price = prices_by_season[r["season"]]["price_chf_per_kwh"][int(r["hour"])]
            e_ac_elec = r["E_ac_kWh"] / config.ETA_MOTOR_ELEC
            e_vent_elec = r["E_vent_kWh"]
            E_ac += e_ac_elec; E_vent += e_vent_elec
            cost_ac += e_ac_elec * price
            cost_vent += e_vent_elec * price
        rows.append({"refrigerant": refrigerant, "bore_mm": bore_mm,
                     "E_ac_kWh": E_ac, "E_vent_kWh": E_vent,
                     "E_total_kWh": E_ac + E_vent,
                     "cost_ac_CHF": cost_ac, "cost_vent_CHF": cost_vent,
                     "cost_total_CHF": cost_ac + cost_vent})
    return pd.DataFrame(rows)
