"""The killable solver pool: results match the in-process solver, an overrun
is killed with SolveTimeout, and the pool keeps working afterwards."""

import time

import pytest

import sandbox


@pytest.fixture(scope='module')
def pool():
    return sandbox.SolverPool(size=1, timeout=5)


def test_solves_in_a_helper(pool):
    # the helper returns exactly what the in-process solver would
    from calculator import solve_job

    result = pool.run('x**2=4')
    assert result == solve_job('x**2=4')
    assert result['solution_latex'] == 'x = -2, 2'


def test_unsolvable_has_no_solution(pool):
    assert pool.run('++')['solution'] is None


def test_overrun_is_stopped_and_pool_recovers(pool):
    # whichever limit trips first stops it: the time limit everywhere, or on
    # Linux the memory cap (the job then reports no solution)
    start = time.perf_counter()
    try:
        result = pool.run('x**(10**4)+x+1=0', timeout=1)
    except sandbox.SolveTimeout:
        pass
    else:
        assert result['solution'] is None
    assert time.perf_counter() - start < 5
    # the killed helper was replaced; the next job runs normally
    assert pool.run('2+2')['solution'] == '4'


def test_checks_in_a_helper(pool):
    from checker import check_lines

    lines = ['2x+3=11', '2x=14']
    assert pool.run({'lines': lines}, kind='check') == check_lines(lines)


def test_check_uses_the_shared_pool():
    result = sandbox.check(['x^2=4', 'x=2'], reveal=True)
    assert result['first_error'] == 1
    assert result['answer_latex'] == 'x = -2, 2'
