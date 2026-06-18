"""Task 1 figures: room air (T, humidity), and AC/ventilation operation over
each representative season-day, plus a four-season overview. Clean labels,
units and legends (graded). Uses a non-interactive backend."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src import config

_MODE_NUM = {"OFF": 0, "VENT": 1, "AC": 2}


def plot_season(r, path):
    th = r["t"] / 60.0
    fig, ax = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)

    # (1) room temperature + acceptable band + hysteresis setpoints
    ax[0].axhspan(config.T_BAND_LOW_C, config.T_BAND_HIGH_C,
                  color="tab:green", alpha=0.12, label="acceptable 15-18 C")
    ax[0].plot(th, r["T"], color="tab:blue", lw=1.6, label="room T")
    ax[0].axhline(config.T_ON_C, color="0.5", ls=":", lw=0.9)
    ax[0].axhline(config.T_OFF_C, color="0.5", ls=":", lw=0.9,
                  label="ON 17.5 / OFF 15.5")
    ax[0].set_ylabel("temperature [C]")
    ax[0].set_title("Server room - %s day  (40 mm / %s stand-in)"
                    % (r["season"], config.STANDIN_REFRIGERANT))
    ax[0].set_ylim(13, 19); ax[0].legend(loc="upper right", fontsize=8)

    # (2) relative humidity (+ allowable band) and humidity ratio
    ax[1].axhspan(100 * config.PHI_ALLOW_LOW, 100 * config.PHI_ALLOW_HIGH,
                  color="tab:orange", alpha=0.08)
    ax[1].plot(th, 100 * r["phi"], color="tab:purple", lw=1.5, label="room RH")
    ax[1].axhline(100 * config.PHI_ALLOW_LOW, color="tab:red", ls="--", lw=0.9,
                  label="allowable 14-80 %")
    ax[1].axhline(100 * config.PHI_ALLOW_HIGH, color="tab:red", ls="--", lw=0.9)
    ax[1].set_ylabel("relative humidity [%]"); ax[1].set_ylim(0, 90)
    ax[1].legend(loc="upper right", fontsize=8)
    axb = ax[1].twinx()
    axb.plot(th, 1000 * r["X"], color="tab:cyan", ls=":", lw=1.3)
    axb.set_ylabel("humidity ratio X [g/kg]", color="tab:cyan")
    axb.tick_params(axis="y", labelcolor="tab:cyan")

    # (3) operating mode + cooling powers
    mode_num = np.array([_MODE_NUM[m] for m in r["mode"]])
    ax[2].step(th, mode_num, where="post", color="k", lw=1.3)
    ax[2].set_yticks([0, 1, 2]); ax[2].set_yticklabels(["OFF", "VENT", "AC"])
    ax[2].set_ylim(-0.3, 2.3); ax[2].set_ylabel("mode")
    axc = ax[2].twinx()
    axc.plot(th, r["Q_dem"], color="tab:red", lw=1.2, label="server load")
    axc.plot(th, r["Q_cool"], color="tab:blue", ls="--", lw=1.2, label="cooling delivered")
    axc.set_ylabel("power [kW]"); axc.set_ylim(0, max(8, r["Q_cool"].max() * 1.1))
    axc.legend(loc="upper right", fontsize=8)
    ax[2].set_xlabel("time of day [h]"); ax[2].set_xlim(0, 24)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_overview(R, path):
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    colors = {"winter": "tab:blue", "spring": "tab:green",
              "summer": "tab:red", "fall": "tab:orange"}
    ax[0].axhspan(config.T_BAND_LOW_C, config.T_BAND_HIGH_C,
                  color="0.85", alpha=0.6)
    for s in config.SEASONS:
        th = R[s]["t"] / 60.0
        ax[0].plot(th, R[s]["T"], color=colors[s], lw=1.3, label=s)
        ax[1].plot(th, 100 * R[s]["phi"], color=colors[s], lw=1.3, label=s)
    ax[0].set_ylabel("room T [C]"); ax[0].set_ylim(13, 19)
    ax[0].set_title("Four representative days - room temperature & humidity")
    ax[0].legend(loc="upper right", ncol=4, fontsize=8)
    ax[1].axhline(100 * config.PHI_ALLOW_LOW, color="tab:red", ls="--", lw=0.9)
    ax[1].set_ylabel("room RH [%]"); ax[1].set_ylim(0, 90)
    ax[1].set_xlabel("time of day [h]"); ax[1].set_xlim(0, 24)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
