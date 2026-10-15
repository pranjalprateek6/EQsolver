import pytest

from calculator import evaluate_expression, solve_equation, solve_expression


class TestEvaluate:
    def test_arithmetic(self):
        assert evaluate_expression('2+3*4') == 14

    def test_division_is_float(self):
        assert evaluate_expression('7/2') == pytest.approx(3.5)

    def test_sqrt(self):
        assert evaluate_expression('sqrt(9)') == 3

    def test_invalid_returns_none(self):
        assert evaluate_expression('++') is None


class TestSolveEquation:
    def test_linear(self):
        assert solve_equation('x+1=3') == [2]

    def test_quadratic(self):
        assert sorted(solve_equation('x**2=4')) == [-2, 2]

    def test_invalid_returns_none(self):
        assert solve_equation('garbage=') is None


class TestSolveExpression:
    def test_plain_arithmetic(self):
        assert solve_expression('8+3') == ('8+3', 11)

    def test_power(self):
        expr, sol = solve_expression('2**(10)')
        assert sol == 1024

    def test_equation(self):
        expr, sol = solve_expression('x**(2)=4')
        assert sorted(sol) == [-2, 2]

    def test_fraction_expression(self):
        # the spatial parser emits explicit fractions like this
        assert solve_expression('((1)/(2))')[1] == pytest.approx(0.5)

    def test_human_operators_normalized(self):
        # typed × and ÷ solve like * and /
        assert solve_expression('6÷2')[1] == 3
        assert solve_expression('3×4')[1] == 12

    def test_empty(self):
        assert solve_expression('   ') == ('', None)

    def test_unsolvable_returns_none(self):
        assert solve_expression('x**2=')[1] is None


class TestSolveJob:
    """solve_job is what the sandbox runs: the solution as text and as LaTeX."""

    def job(self, expression):
        from calculator import solve_job
        return solve_job(expression)

    def test_roots_use_the_real_variable(self):
        assert self.job('y**2=9')['solution_latex'] == 'y = -3, 3'

    def test_single_root(self):
        assert self.job('2x+1=5')['solution_latex'] == 'x = 2'

    def test_exact_fraction_with_decimal(self):
        assert self.job('7/2')['solution_latex'] == r'\frac{7}{2} = 3.5'

    def test_irrational_is_approximated(self):
        assert self.job('sqrt(2)')['solution_latex'] == r'\sqrt{2} \approx 1.41421'

    def test_integer_is_plain(self):
        job = self.job('8+3')
        assert job['solution'] == '11' and job['solution_latex'] == '11'

    def test_identity(self):
        job = self.job('x+1=1+x')
        assert job['solution'] == 'all values'

    def test_contradiction(self):
        job = self.job('2=3')
        assert job['solution'] == '[]'
        assert 'no solution' in job['solution_latex']

    def test_complex_roots(self):
        assert self.job('x**2=-1')['solution_latex'] == 'x = - i, i'

    def test_unsolved_has_no_latex(self):
        job = self.job('x+1')
        assert job['solution'] is None and job['solution_latex'] == ''
