"""
shear.py -- distribution of shear rate in an OpenFOAM case, in the fluid volume and on the walls.

    from cfdtools import shear

    shear.write_fields(case)                  # once per case: OpenFOAM writes grad(U) and the cell volumes V
    vol = shear.volume_samples(case)          # shear rate of every cell, weighted by cell volume
    wall = shear.wall_samples(case)           # shear rate of every wall face, weighted by face area
    shear.summary(vol)                        # weighted percentiles, fractions below 1, 10, 100, 1000 1/s
    shear.plot_cdf(ax, vol, label="volume")   # share of the volume (or wall area) below each shear rate

The shear rate is gamma_dot = sqrt(2 D:D), with D the symmetric part of grad(U): the definition OpenFOAM's
viscosity models use (sqrt(2) mag(symm(grad(U)))). grad(U) is OpenFOAM's own (postProcess -func "grad(U)"). On a
wall, its normal component comes from the wall-normal velocity gradient (snGrad), so the wall values are the wall
shear rate. In an axisymmetric wedge, the cell volumes already include the radius, so the volume distribution is
that of the full annulus.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import numpy as np

from cfdtools import post

GRAD = "grad(U)"
VOLUME = "V"


class Samples(NamedTuple):
    """Shear rate (1/s) and weight (cell volume, m^3, or face area, m^2) of each cell or face."""
    shear_rate: np.ndarray
    weight: np.ndarray
    time: float
    label: np.ndarray = None        # patch name of each wall face (wall_samples only)


def write_fields(case, time="latest"):
    """Run OpenFOAM's postProcess on `case` to write grad(U) and the cell volumes V at one saved time.

    time : "latest", or a saved time value. Needs the `openfoam` launcher (openfoam-app); otherwise run, in an
    OpenFOAM shell:  postProcess -case <case> -funcs '(grad(U) writeCellVolumes)' -latestTime
    """
    launcher = shutil.which("openfoam")
    if launcher is None:
        raise RuntimeError("openfoam launcher not found; run in an OpenFOAM shell: "
                           f"postProcess -case {case} -funcs '(grad(U) writeCellVolumes)' -latestTime")
    when = ["-latestTime"] if time == "latest" else ["-time", str(time)]
    cmd = [launcher, "postProcess", "-case", str(case), "-funcs", "(grad(U) writeCellVolumes)", *when]
    env = {**os.environ, "TERM": os.environ.get("TERM") or "dumb"}     # no terminal (e.g. a notebook)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"postProcess failed in {case}:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}")
    return result.stdout


def shear_rate(grad):
    """sqrt(2 D:D), D = symm(grad U), for each row of a (n, 9) array of velocity gradients."""
    g = np.asarray(grad, dtype=float).reshape(-1, 3, 3)
    d = 0.5 * (g + g.transpose(0, 2, 1))
    return np.sqrt(2.0 * np.einsum("nij,nij->n", d, d))


def wall_patches(case):
    """Names of the patches of type wall, from constant/polyMesh/boundary (read directly: PyFoam calls tput)."""
    text = (Path(case) / "constant" / "polyMesh" / "boundary").read_text()
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)         # drop comments
    body = text[text.index("(", text.index("}")) + 1:]                 # the patch list, after the FoamFile header
    return [name for name, entry in re.findall(r"([\w\"().|-]+)\s*\{([^}]*)\}", body)
            if re.search(r"\btype\s+wall\s*;", entry)]


def volume_samples(case, time="latest"):
    """Shear rate of every cell, weighted by its volume. Run write_fields(case) first."""
    mesh, t = post.read_case(case, time)
    missing = [f for f in (GRAD, VOLUME) if f not in mesh.cell_data]
    if missing:
        raise KeyError(f"{missing} not in {case} at time {t}; run shear.write_fields(case) first")
    return Samples(shear_rate(mesh.cell_data[GRAD]), np.asarray(mesh.cell_data[VOLUME], dtype=float), t)


def wall_samples(case, time="latest", patches=None):
    """Shear rate of every wall face, weighted by its area. patches: names, or None for all wall patches."""
    rates, areas, labels, t = [], [], [], None
    for name in patches or wall_patches(case):
        patch, t = post.read_patch(case, name, time)
        if GRAD not in patch.cell_data:
            raise KeyError(f"{GRAD} not on patch {name} in {case}; run shear.write_fields(case) first")
        rates.append(shear_rate(patch.cell_data[GRAD]))
        areas.append(np.asarray(patch.compute_cell_sizes(length=False, area=True, volume=False)["Area"]))
        labels.append(np.full(patch.n_cells, name))
    return Samples(np.concatenate(rates), np.concatenate(areas), t, np.concatenate(labels))


def quantiles(samples, q=(0.05, 0.25, 0.5, 0.75, 0.95)):
    """Weighted quantiles of the shear rate: the shear rate below which a fraction q of the volume (area) lies."""
    order = np.argsort(samples.shear_rate)
    rate, w = samples.shear_rate[order], samples.weight[order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()          # mid-point rule
    return np.interp(q, cum, rate)


def fraction_below(samples, rates):
    """Fraction of the volume (area) with a shear rate below each of `rates`."""
    rates = np.atleast_1d(rates)
    return np.array([samples.weight[samples.shear_rate < r].sum() for r in rates]) / samples.weight.sum()


def summary(samples, q=(0.05, 0.25, 0.5, 0.75, 0.95), below=(1, 10, 100, 1000)):
    """Weighted percentiles and fractions below a few shear rates, as a dict."""
    out = {f"p{round(100 * x):g} (1/s)": v for x, v in zip(q, quantiles(samples, q))}
    out.update({f"below {r:g} 1/s": f for r, f in zip(below, fraction_below(samples, below))})
    out["weighted mean (1/s)"] = np.average(samples.shear_rate, weights=samples.weight)
    out["max (1/s)"] = samples.shear_rate.max()
    return out


def distribution(samples, bins_per_decade=10, lo=None, hi=None):
    """Weighted distribution on log-spaced bins.

    Returns (edges, density, cdf): density is the fraction of volume (area) per decade of shear rate, so it reads
    the same whatever the bin width; cdf is the fraction below each edge. Shear rates below `lo` are counted in
    the first bin.
    """
    rate = samples.shear_rate
    positive = rate[rate > 0]
    lo = lo or 10 ** np.floor(np.log10(positive.min()))
    hi = hi or 10 ** np.ceil(np.log10(rate.max()))
    edges = np.logspace(np.log10(lo), np.log10(hi), int(round(np.log10(hi / lo) * bins_per_decade)) + 1)
    counts, _ = np.histogram(np.clip(rate, lo, hi), bins=edges, weights=samples.weight)
    frac = counts / samples.weight.sum()
    density = frac / np.diff(np.log10(edges))
    cdf = np.concatenate([[0.0], np.cumsum(frac)])
    return edges, density, cdf


def plot_cdf(ax, samples, label=None, **kwargs):
    """Share of the volume (area) below each shear rate, on a log shear-rate axis."""
    order = np.argsort(samples.shear_rate)
    rate, w = samples.shear_rate[order], samples.weight[order]
    line, = ax.step(rate, np.cumsum(w) / w.sum(), where="post", label=label, **kwargs)
    ax.set_xscale("log")
    ax.set_ylim(0, 1)
    ax.set_xlabel(r"Shear rate $\dot\gamma$ (s$^{-1}$)")
    ax.set_ylabel("Cumulative fraction")
    return line


def plot_density(ax, samples, label=None, bins_per_decade=10, **kwargs):
    """Fraction of the volume (area) per decade of shear rate, as a step line on a log axis."""
    edges, density, _ = distribution(samples, bins_per_decade)
    patch = ax.stairs(density, edges, label=label, **kwargs)
    ax.set_xscale("log")
    ax.set_xlabel(r"Shear rate $\dot\gamma$ (s$^{-1}$)")
    ax.set_ylabel("Fraction per decade")
    return patch
