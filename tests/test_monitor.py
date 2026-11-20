"""cfdtools.monitor on small postProcessing trees laid out the way OpenFOAM writes them."""

import os

from cfdtools.monitor import NOISE_RATIO, active_case, find_series, read_dat, select

HEADER = "# Moment\n# CofR : (0 0 0)\n#\n# Time\ttotal_x\ttotal_y\ttotal_z\n"

SOLVER_INFO = (
    "# Solver information\n"
    "# Time\tU_solver\tUx_initial\tUx_final\tUx_iters\tU_converged"
    "\tp_solver\tp_initial\tp_final\tp_iters\tp_converged\n"
    "1\tsmoothSolver\t1\t1e-06\t3\tfalse\tGAMG\t1\t1e-04\t12\tfalse\n"
    "2\tsmoothSolver\t0.2\t1e-07\t2\tfalse\tGAMG\t0.5\t1e-05\t10\tfalse\n"
)


def write(path, text, mtime=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


def rows(times, offset):
    """Data lines with total_x = offset + time, so each file's rows can be told apart."""
    return "".join(f"{t}\t{offset + t}\t0\t0\n" for t in times)


def test_plain_run(tmp_path):
    f = write(tmp_path / "postProcessing/torque/0/moment.dat", HEADER + rows([1, 2, 3], 10))
    series = find_series(tmp_path)
    assert series == {"torque/moment": [f]}
    assert read_dat(series["torque/moment"]) == {
        "Time": [1, 2, 3], "total_x": [11, 12, 13], "total_y": [0, 0, 0], "total_z": [0, 0, 0],
    }


def test_rerun_uses_only_the_newest_run(tmp_path):
    root = tmp_path / "postProcessing/torque"
    write(root / "0/moment.dat", HEADER + rows([1, 2, 3, 4], 10), mtime=1000)
    write(root / "3/moment.dat", HEADER + rows([4, 5], 10), mtime=1500)   # that run's restart
    rerun = write(root / "0/moment_0.dat", HEADER + rows([1, 2], 20), mtime=2000)
    series = find_series(tmp_path)
    assert series == {"torque/moment": [rerun]}
    assert read_dat(series["torque/moment"])["total_x"] == [21, 22]


def test_restart_replaces_the_overlap(tmp_path):
    root = tmp_path / "postProcessing/torque"
    first = write(root / "0/moment.dat", HEADER + rows([1, 2, 3, 4, 5], 10), mtime=1000)
    # Restarted from the time-3 save after the first run had reached time 5.
    restart = write(root / "3/moment.dat", HEADER + rows([4, 5, 6, 7], 20), mtime=2000)
    series = find_series(tmp_path)
    assert series == {"torque/moment": [first, restart]}
    columns = read_dat(series["torque/moment"])
    assert columns["Time"] == [1, 2, 3, 4, 5, 6, 7]
    assert columns["total_x"] == [11, 12, 13, 24, 25, 26, 27]


def test_line_still_being_written_is_skipped(tmp_path):
    f = write(tmp_path / "moment.dat", HEADER + rows([1, 2], 10) + "3\t13")
    assert read_dat([f])["Time"] == [1, 2]


def test_vector_columns_in_parentheses(tmp_path):
    f = write(tmp_path / "moment.dat", HEADER + "1\t(1 2 3)\n2\t(4 5 6)\n")
    assert read_dat([f]) == {"Time": [1, 2], "total_x": [1, 4], "total_y": [2, 5], "total_z": [3, 6]}


def test_non_numeric_columns_are_dropped(tmp_path):
    columns = read_dat([write(tmp_path / "solverInfo.dat", SOLVER_INFO)])
    assert set(columns) == {"Time", "Ux_initial", "Ux_final", "Ux_iters", "p_initial", "p_final", "p_iters"}
    assert columns["p_iters"] == [12, 10]


def test_select_keeps_only_initial_residuals():
    columns = {"Time": [1, 2], "Ux_initial": [1, 0.2], "Ux_final": [1e-6, 1e-7], "Ux_iters": [3, 2],
               "p_initial": [1, 0.5], "p_final": [1e-4, 1e-5], "p_iters": [12, 10]}
    assert select("residuals/solverInfo", columns) == (
        [1, 2], {"Ux_initial": [1, 0.2], "p_initial": [1, 0.5]}, True)


def test_select_drops_columns_that_are_noise_next_to_the_peak():
    peak = 2.0
    columns = {
        "Time": [1, 2],
        "total_z": [-1.0, -peak],                      # largest magnitude in the file
        "total_x": [10 * NOISE_RATIO * peak, 0.0],
        "total_y": [0.1 * NOISE_RATIO * peak, 0.0],
    }
    time, picked, log_y = select("torque/moment", columns)
    assert time == [1, 2]
    assert set(picked) == {"total_z", "total_x"}
    assert not log_y


def make_case(path, dat_mtime):
    write(path / "system/controlDict", "")
    write(path / "postProcessing/torque/0/moment.dat", HEADER, mtime=dat_mtime)
    return path


def test_active_case_follows_the_case_writing_now(tmp_path):
    slow = make_case(tmp_path / "rpm_100", dat_mtime=2000)
    fast = make_case(tmp_path / "rpm_200", dat_mtime=1000)
    assert active_case(tmp_path) == slow
    os.utime(fast / "postProcessing/torque/0/moment.dat", (3000, 3000))
    assert active_case(tmp_path) == fast
    assert active_case(slow) == slow
