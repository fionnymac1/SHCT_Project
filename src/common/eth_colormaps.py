"""
eth_colormaps
=============

ETH-Zürich-branded *sequential* colormaps for matplotlib.

Each map is a single-hue ramp anchored on one official ETH corporate-design
colour, built so that lightness (L*, measured in CAM02-UCS) increases
monotonically and near-linearly across the map. This is the property
matplotlib's guide requires of a *sequential* colormap; the six raw ETH
brand colours on their own are *categorical* (all near mid-lightness) and do
NOT form a valid sequential map.

Convention (matches matplotlib's built-in `Blues`, `Greens`, ...):
    data low  -> light end
    data high -> dark, saturated ETH colour
Reversed variants are registered with the usual `_r` suffix.

Usage
-----
    import eth_colormaps                      # registers the maps on import
    import matplotlib.pyplot as plt
    plt.imshow(data, cmap="ETHBlue")          # or "ETHBlue_r", "ETHPetrol", ...

    # or grab the object directly:
    cmap = eth_colormaps.cmaps["Blue"]

Requires: numpy, matplotlib, colorspacious.
"""
from __future__ import annotations

import os
import numpy as np
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, to_rgb
from colorspacious import cspace_converter

# Official ETH corporate-design colours (verified against the ETH web-colours
# definitions; identical values are used by the R `unicol`/`unikn` packages).
ETH_COLORS: dict[str, str] = {
    "Blue":   "#215CAF",
    "Petrol": "#007894",
    "Green":  "#627313",
    "Red":    "#B7352D",
    "Purple": "#A7117A",
    "Grey":   "#6F6F6F",
}

_N = 256
_rgb2ucs = cspace_converter("sRGB1", "CAM02-UCS")
_ucs2rgb = cspace_converter("CAM02-UCS", "sRGB1")


def make_sequential(hex_color: str, n: int = _N,
                    J_light: float = 96.0, J_dark: float = 22.0,
                    tint: float = 0.12) -> LinearSegmentedColormap:
    """Return a single-hue sequential cmap, light->dark, linear in CAM02-UCS L*.

    Linear interpolation of the J' (lightness) coordinate guarantees monotonic,
    near-uniform lightness by construction. Endpoints J_light/J_dark set the
    lightness ceiling/floor; `tint` controls how strongly the light end keeps
    the hue (smaller -> closer to white).
    """
    base = np.array(to_rgb(hex_color))

    dark = _rgb2ucs(np.clip(base * 0.55, 0, 1)).copy()
    dark[0] = J_dark
    light = _rgb2ucs(np.clip(base + (1 - base) * (1 - tint), 0, 1)).copy()
    light[0] = J_light

    t = np.linspace(0, 1, n)[:, None]
    rgb = np.clip(_ucs2rgb(light[None] * (1 - t) + dark[None] * t), 0, 1)
    return LinearSegmentedColormap.from_list(f"ETH{_name_of(hex_color)}", rgb, N=n)


def _name_of(hex_color: str) -> str:
    for k, v in ETH_COLORS.items():
        if v.lower() == hex_color.lower():
            return k
    return "Custom"


def make_sequential_multihue(hex_list, J=(18, 40, 58, 76, 92),
                             name="ETHmulti", n=_N) -> LinearSegmentedColormap:
    """Viridis-style multi-hue sequential map built from ETH hues.

    Sweeps hue through `hex_list` (ordered dark->light) while OVERRIDING each
    anchor's lightness with the monotone increasing values in `J`. Because the
    J nodes are monotone and interpolation is linear in CAM02-UCS, lightness is
    monotone by construction. The hue sweep gives viridis-like step
    discriminability that a single-hue ramp cannot.

    len(J) must equal len(hex_list). Colours are the ETH *hues*, not their
    nominal hex values (lightness is reassigned), so this is "ETH-flavoured"
    rather than literally the seven brand colours.
    """
    assert len(J) == len(hex_list), "J must have one lightness per anchor"
    ucs = np.array([_rgb2ucs(np.array(to_rgb(h))) for h in hex_list], float)
    ucs[:, 0] = np.asarray(J, float)
    tn = np.linspace(0, 1, len(hex_list))
    t = np.linspace(0, 1, n)
    out = np.stack([np.interp(t, tn, ucs[:, c]) for c in range(3)], axis=1)
    rgb = np.clip(_ucs2rgb(out), 0, 1)
    return LinearSegmentedColormap.from_list(name, rgb, N=n)


def lightness(cmap: LinearSegmentedColormap, n: int = _N) -> np.ndarray:
    """CAM02-UCS L* along the colormap (for verification/plots)."""
    x = np.linspace(0, 1, n)
    return _rgb2ucs(cmap(x)[:, :3][None])[0, :, 0]


def is_monotonic(cmap: LinearSegmentedColormap) -> bool:
    """True if lightness changes monotonically (the sequential criterion)."""
    d = np.diff(lightness(cmap))
    return bool(np.all(d <= 1e-6) or np.all(d >= -1e-6))


def preview(names=None, with_lightness: bool = True, save: str | bool | None = None):
    """Show the colormaps as gradient-strip boxes (the 'little boxes').

    Parameters
    ----------
    names : list[str] or None
        Which cmaps to show, e.g. ["Blue", "Petrol"]. None -> every registered
        cmap (the seven single-hue ETH* maps plus multi/warm/cividis).
    with_lightness : bool
        If True, draw the CAM02-UCS L* profile next to each strip.
    save : str, False, or None
        Path to save the figure to. None (default) -> figures/
        eth_colormaps_preview.png, resolved relative to the repo root
        regardless of cwd. Pass False to skip saving and just return the
        Figure.

    Returns the Matplotlib Figure.
    """
    import matplotlib.pyplot as plt

    names = names or list(cmaps)
    if save is None:
        _repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        save = os.path.join(_repo, "figures", "eth_colormaps_preview.png")
    grad = np.vstack([np.linspace(0, 1, 256)] * 2)
    x = np.linspace(0, 1, 256)
    ncols = 2 if with_lightness else 1

    fig, axes = plt.subplots(
        len(names), ncols, figsize=(9 if with_lightness else 6, 1.25 * len(names)),
        squeeze=False,
        gridspec_kw={"width_ratios": [3, 2]} if with_lightness else None,
    )
    for i, name in enumerate(names):
        cm = cmaps[name]
        axes[i, 0].imshow(grad, aspect="auto", cmap=cm)
        axes[i, 0].set_axis_off()
        axes[i, 0].text(-0.02, 0.5, f"ETH {name}", va="center", ha="right",
                        transform=axes[i, 0].transAxes, fontsize=10)
        if with_lightness:
            ok = is_monotonic(cm)
            axes[i, 1].scatter(x, lightness(cm), c=x, cmap=cm, s=12, linewidths=0)
            axes[i, 1].set_ylim(0, 100); axes[i, 1].set_xlim(0, 1)
            axes[i, 1].set_yticks([0, 50, 100]); axes[i, 1].set_xticks([])
            axes[i, 1].set_ylabel("L*", fontsize=8)
            axes[i, 1].set_title("monotonic" if ok else "NOT monotonic",
                                 fontsize=8, color=("0.4" if ok else "red"))
    fig.tight_layout()
    if save:
        os.makedirs(os.path.dirname(save), exist_ok=True)
        fig.savefig(save, dpi=130, bbox_inches="tight")
        print("Preview written to %s" % save)
    return fig


# Build, verify, and register all seven single-hue ramps on import.
cmaps: dict[str, LinearSegmentedColormap] = {}
for _name, _hex in ETH_COLORS.items():
    _cm = make_sequential(_hex)
    assert is_monotonic(_cm), f"ETH{_name} is not monotonic in L*"
    cmaps[_name] = _cm
    for _c in (_cm, _cm.reversed()):
        try:
            mpl.colormaps.register(_c, force=True)
        except Exception:
            pass  # already registered

# Multi-hue (viridis-style) ETH map: purple -> blue -> petrol -> green -> light.
# Recommended for dense scientific fields (e.g. contour/COP maps) where step
# discriminability matters more than single-hue branding.
_multi = make_sequential_multihue(
    [ETH_COLORS["Purple"], ETH_COLORS["Blue"], ETH_COLORS["Petrol"],
     ETH_COLORS["Green"], ETH_COLORS["Green"]], name="ETHmulti")
assert is_monotonic(_multi), "ETHmulti is not monotonic in L*"
cmaps["multi"] = _multi
for _c in (_multi, _multi.reversed()):
    try:
        mpl.colormaps.register(_c, force=True)
    except Exception:
        pass

# Warm / "heat" ETH map (plasma/inferno/magma niche): black -> purple -> red ->
# yellow-gold (the former bronze anchor is now WARM_GOLD too, just darker --
# J still ramps 78->95 so the final stretch stays monotonic, just monochromatic
# gold instead of bronze->gold). WARM_GOLD is ETH-flavoured, not a literal
# brand colour (ETH has no yellow). Swap it to taste:
#   muted   "#C9A94E"  |  warm "#DFC04A"  |  yellow-gold "#ECD636"  |  bright "#F6E920"
# Public (no leading underscore): config.py reuses this exact value for its
# categorical "g2" accent swatch, so the two stay in sync from one definition.
WARM_GOLD = "#ECD636"
_warm = make_sequential_multihue(
    ["#000000", ETH_COLORS["Purple"], ETH_COLORS["Red"], WARM_GOLD,
     WARM_GOLD], J=(4, 30, 55, 78, 95), name="ETHwarm")
assert is_monotonic(_warm), "ETHwarm is not monotonic in L*"
cmaps["warm"] = _warm
for _c in (_warm, _warm.reversed()):
    try:
        mpl.colormaps.register(_c, force=True)
    except Exception:
        pass

# Low-chroma, maximally colour-blind-safe ETH map (cividis niche):
# ETH Blue -> neutral grey -> yellow-gold. Avoids red and green entirely (the
# axis colour-vision-deficient viewers struggle with) and keeps chroma low, so
# it reads almost identically under deuteranopia. Use this for figures that must
# survive colour-blind readers or grayscale printing.
_cividis = make_sequential_multihue(
    [ETH_COLORS["Blue"], ETH_COLORS["Grey"], "#E3CC55"],
    J=(15, 52, 92), name="ETHcividis")
assert is_monotonic(_cividis), "ETHcividis is not monotonic in L*"
cmaps["cividis"] = _cividis
for _c in (_cividis, _cividis.reversed()):
    try:
        mpl.colormaps.register(_c, force=True)
    except Exception:
        pass

# ETH qualitative (categorical) palette: for DISCRETE data -- lines, bars,
# legend-distinguished groups -- as opposed to the cmaps dict above (all
# continuous/sequential; do not use cmaps["qual"] for contour/heatmap data).
# Order matters: it's also matplotlib's default line-cycle order via
# set_eth_cycle(). Black first (max contrast, "neutral"/reference roles), then
# the six ETH hues, then the WARM_GOLD accent in the "Orange"-equivalent slot.
ETH_QUAL: dict[str, str] = {
    "Black": "#000000",
    "Blue": ETH_COLORS["Blue"],
    "Petrol": ETH_COLORS["Petrol"],
    "Green": ETH_COLORS["Green"],
    "Gold": WARM_GOLD,
    "Red": ETH_COLORS["Red"],
    "Purple": ETH_COLORS["Purple"],
    "Grey": ETH_COLORS["Grey"],
}
ETH_QUAL_LIST = list(ETH_QUAL.values())
_qual = ListedColormap(ETH_QUAL_LIST, name="ETHqual")
cmaps["qual"] = _qual
try:
    mpl.colormaps.register(_qual, force=True)
except Exception:
    pass


def eth_cycle(n: int | None = None) -> list[str]:
    """Return the ETH qualitative colours as a hex list (first `n` if given)."""
    return ETH_QUAL_LIST[:n] if n else list(ETH_QUAL_LIST)


def set_eth_cycle(n: int | None = None) -> None:
    """Set Matplotlib's default line/category colour cycle to the ETH palette."""
    from cycler import cycler
    mpl.rcParams["axes.prop_cycle"] = cycler(color=eth_cycle(n))


def qualitative_preview(save: str | None = None, simulate_cvd: bool = True):
    """Swatch chart of the ETH qualitative palette; optionally a deuteranope row."""
    import matplotlib.pyplot as plt
    from colorspacious import cspace_convert
    names = list(ETH_QUAL)
    rows = 2 if simulate_cvd else 1
    fig, axes = plt.subplots(rows, 1, figsize=(8, 1.1 * rows + 0.4), squeeze=False)
    def draw(ax, sim):
        for i, (nm, hx) in enumerate(ETH_QUAL.items()):
            c = to_rgb(hx)
            if sim:
                c = tuple(np.clip(cspace_convert(
                    np.array(c), {"name": "sRGB1+CVD", "cvd_type": "deuteranomaly",
                                  "severity": 100}, "sRGB1"), 0, 1))
            ax.add_patch(plt.Rectangle((i, 0), 1, 1, color=c))
            ax.text(i + 0.5, -0.18, nm, ha="center", va="top", fontsize=9)
        ax.set_xlim(0, len(names)); ax.set_ylim(-0.4, 1)
        ax.set_axis_off()
    draw(axes[0, 0], False); axes[0, 0].set_title("ETH qualitative palette", fontsize=12)
    if simulate_cvd:
        draw(axes[1, 0], True)
        axes[1, 0].set_title("as seen with deuteranopia (red-green)", fontsize=10)
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=140, bbox_inches="tight")
    return fig


__all__ = ["ETH_COLORS", "WARM_GOLD", "ETH_QUAL", "ETH_QUAL_LIST", "cmaps",
           "make_sequential", "make_sequential_multihue", "lightness", "is_monotonic",
           "preview", "eth_cycle", "set_eth_cycle", "qualitative_preview"]

if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")          # headless: write a PNG, do not require a display
    preview()
    _repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    qualitative_preview(save=os.path.join(_repo, "figures", "eth_qualitative_preview.png"))
