"""Step-by-step working: computed by SymPy, always agreeing with the answer."""
from calculator import solve_job


def steps(expression):
    return solve_job(expression)['steps']


def titles(expression):
    return [s['title'] for s in steps(expression)]


def last(expression):
    return steps(expression)[-1]['latex']


class TestLinear:
    def test_collect_then_divide(self):
        assert titles('2x+1=5') == [
            'Start with the equation',
            'Move the x terms to one side and the numbers to the other',
            'Divide both sides by 2',
        ]
        assert last('2x+1=5') == 'x = 2'

    def test_clears_fractions_first(self):
        s = steps('(x+1)/2=4')
        assert s[1]['title'] == 'Multiply both sides by 2 to clear the fractions'
        assert s[1]['latex'] == 'x + 1 = 8'
        assert s[-1]['latex'] == 'x = 7'

    def test_variable_on_the_right_ends_positive(self):
        # no detour through -x = -5
        assert last('5=x') == 'x = 5'
        assert not any('-1' in t for t in titles('5=x'))

    def test_uses_the_real_variable(self):
        assert titles('3y-2=7')[1] == 'Move the y terms to one side and the numbers to the other'
        assert last('3y-2=7') == 'y = 3'


class TestQuadratic:
    def test_factors_rational_roots(self):
        t = titles('x^2=2x+8')
        assert t[1:] == ['Bring everything to one side', 'Factor',
                         'Set each factor equal to zero', 'Solve each one']
        assert last('x^2=2x+8') == 'x = -2, 4'

    def test_skips_rearranging_when_already_standard(self):
        assert 'Bring everything to one side' not in titles('x^2-5x+6=0')

    def test_quadratic_formula_for_irrational_roots(self):
        t = titles('x^2-2=0')
        assert 'Use the quadratic formula' in t
        assert steps('x^2-2=0')[-1]['latex'].endswith(r'x = - \sqrt{2}, \sqrt{2}')

    def test_negative_discriminant_is_explained(self):
        assert any('complex' in t for t in titles('x^2+x+1=0'))


class TestSpecialCases:
    def test_identity(self):
        assert last('x+1=x+1') == r'\text{true for every value}'

    def test_contradiction(self):
        assert last('x+1=x+2') == r'\text{no solution}'

    def test_final_step_matches_the_answer(self):
        for expression in ['2x+1=5', '(x+1)/2=4', 'x^2=2x+8', 'y^2=9', '3(x+1)=9']:
            job = solve_job(expression)
            assert job['steps'][-1]['latex'] == job['solution_latex'], expression


class TestNoSteps:
    def test_arithmetic_has_no_steps(self):
        assert steps('8+3') == []

    def test_several_variables(self):
        assert steps('x+y=3') == []

    def test_higher_degree(self):
        assert steps('x^3=8') == []

    def test_variable_in_denominator(self):
        assert steps('1/x=2') == []

    def test_unparseable(self):
        assert steps('++') == []
