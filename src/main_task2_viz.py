"""
Task 2 visualization entry point. Run from the repository root:
    python -m src.main_task2_viz

Loads the AC performance maps written by main_task2.py (via data_io - same
module owns both the save and the load) and renders the COP_inner / Q_AC_kW
grid of contour plots (one subplot per refrigerant x bore) via visualization.py.
"""
import os
import config, data_io, visualization


def main():
    maps = data_io.load_all_performance_maps()

    os.makedirs("figures", exist_ok=True)
    for value in ("COP_inner", "Q_AC_kW"):
        fig = visualization.visualize_all_maps(maps, value=value, save=False)
        path = os.path.join("figures", "task2_%s_grid.png" % value)
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print("Wrote %s" % path)

    return maps


if __name__ == "__main__":
    main()
