"""cfdtools.convergence.gci against the worked example of Celik et al. (2008)."""

import pytest

from cfdtools.convergence import gci

# Celik et al. (2008), J. Fluids Eng. 130, 078001, Table 1, first column: 2D meshes of
# 18000, 8000 and 4500 cells. gci takes them coarse to fine.
VALUES = [5.863, 5.972, 6.063]
CELLS = [4500, 8000, 18000]


def test_celik_table_1():
    r = gci(VALUES, CELLS, dim=2)
    # Each tolerance is half a unit in the last digit the paper prints.
    assert r["r21"] == pytest.approx(1.5)
    assert r["r32"] == pytest.approx(1.333, abs=5e-4)
    assert r["p"] == pytest.approx(1.53, abs=5e-3)
    assert r["extrapolated"] == pytest.approx(6.1685, abs=5e-5)
    assert r["error_fine"] == pytest.approx(0.015, abs=5e-4)            # e_a21 = 1.5 %
    assert r["error_extrapolated"] == pytest.approx(0.017, abs=5e-4)    # e_ext21 = 1.7 %
    assert r["gci_fine"] == pytest.approx(0.022, abs=5e-4)              # GCI_fine21 = 2.2 %
    assert not r["oscillatory"]


def test_values_that_go_up_then_down_are_oscillatory():
    assert gci([1.0, 1.2, 1.1], CELLS, dim=2)["oscillatory"]


def test_meshes_given_fine_first_are_rejected():
    with pytest.raises(ValueError):
        gci(VALUES[::-1], CELLS[::-1], dim=2)
