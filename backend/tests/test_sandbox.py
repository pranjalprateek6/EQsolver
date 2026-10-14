"""The killable solver pool: results match the in-process solver, an overrun
is killed with SolveTimeout, and the pool keeps working afterwards."""
import time

import pytest

import sandbox


@pytest.fixture(scope='module')
def pool():
    return sandbox.SolverPool(size=1, timeout=5)


def test_solves_in_a_helper(pool):
    result = pool.run('x**2=4')
    assert result == {'expression': 'x**2=4', 'solution': '[-2, 2]', 'latex': 'x^{2} = 4'}


def test_unsolvable_has_no_solution(pool):
    assert pool.run('++')['solution'] is None


def test_overrun_is_killed_and_pool_recovers(pool):
    start = time.perf_counter()
    with pytest.raises(sandbox.SolveTimeout):
        pool.run('x**(10**4)+x+1=0', timeout=1)
    assert time.perf_counter() - start < 5
    # the killed helper was replaced; the next job runs normally
    assert pool.run('2+2')['solution'] == '4'
