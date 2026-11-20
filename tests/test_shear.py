"""cfdtools.shear: the shear rate of known velocity gradients, and weighted statistics of hand-built samples."""

import numpy as np
import pytest

from cfdtools.shear import Samples, distribution, fraction_below, quantiles, shear_rate


def samples(rates, weights):
    return Samples(np.array(rates, dtype=float), np.array(weights, dtype=float), time=0.0)


def bin_fractions(edges, density):
    """Fraction of the weight in each bin: density is per decade of shear rate."""
    return density * np.diff(np.log10(edges))


def test_shear_rate():
    g, e = 4.0, 3.0
    gradients = [
        [[0, g, 0], [0, 0, 0], [0, 0, 0]],              # simple shear, du_x/dy = g
        [[0, -g, 0], [0, 0, 0], [0, 0, 0]],             # the same shear, reversed
        [[0, g, 0], [-g, 0, 0], [0, 0, 0]],             # rigid rotation
        [[e, 0, 0], [0, -e / 2, 0], [0, 0, -e / 2]],    # uniaxial extension
    ]
    expected = [g, g, 0.0, np.sqrt(3) * e]
    assert shear_rate(np.reshape(gradients, (-1, 9))) == pytest.approx(expected)


def test_quantiles_are_weighted():
    # 40 % of the weight sits at 100 1/s, spanning cumulative fractions 0.3 to 0.7, so the
    # weighted median is 100 1/s. The median of the five unweighted values is 10 1/s.
    s = samples([1000, 1, 100, 5, 10], [3, 1, 4, 1, 1])
    assert quantiles(s, [0.5]) == pytest.approx([100.0])


def test_fraction_below():
    s = samples([1, 10, 100], [2, 3, 5])
    assert fraction_below(s, [0.5, 5, 50, 500]) == pytest.approx([0.0, 0.2, 0.5, 1.0])


def test_distribution_sums_to_one():
    # A cell at rest (rate 0) is below every bin, so it is counted in the first.
    s = samples([0, 0.3, 2, 15, 400, 5000], [1, 2, 3, 4, 5, 6])
    edges, density, cdf = distribution(s)
    fractions = bin_fractions(edges, density)
    assert fractions.sum() == pytest.approx(1.0)
    assert fractions[0] == pytest.approx(1 / 21)
    assert cdf[-1] == pytest.approx(1.0)


@pytest.mark.xfail(strict=True, reason=(
    "distribution() clips rates below lo to lo, but the first edge np.logspace builds is "
    "10**log10(lo), which for lo=5 is 5.000000000000001 > 5, so np.histogram drops those rates"))
def test_distribution_counts_rates_below_lo_in_the_first_bin():
    s = samples([1, 10, 100], [1, 1, 1])
    fractions = bin_fractions(*distribution(s, lo=5)[:2])
    assert fractions[0] == pytest.approx(1 / 3)
    assert fractions.sum() == pytest.approx(1.0)
