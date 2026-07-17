import pytest

from calculator import (
    calculate,
    evaluate_expression,
    solve_equation,
    solve_text,
    substitute,
)


class TestArithmetic:
    def test_addition(self):
        assert calculate('2t3') == ('2+3', 5)

    def test_precedence(self):
        assert calculate('2t3x4') == ('2+3*4', 14)

    def test_multi_digit(self):
        assert calculate('12t34') == ('12+34', 46)

    def test_division(self):
        formatted, result = calculate('8L2')
        assert formatted == '8/2'
        assert result == 4

    def test_misread_digits(self):
        # D->0, G->6, B->8, Z->2, f->7, g->9, b->6
        assert calculate('DtG') == ('0+6', 6)
        assert calculate('BtZ') == ('8+2', 10)
        assert calculate('ftg') == ('7+9', 16)

    def test_invalid_expression_returns_none(self):
        formatted, result = calculate('++')
        assert result is None


class TestEquations:
    def test_linear(self):
        # S -> '='
        assert calculate('xt2S5') == ('x+2=5', [3])

    def test_multi_digit_equation(self):
        # regression: consecutive digits used to be dropped in the
        # implicit-operator pass ('12+x=48' became '1+x=48')
        assert calculate('12txS48') == ('12+x=48', [36])

    def test_quadratic(self):
        # 'x2' means x squared
        formatted, solutions = calculate('x2S4')
        assert formatted == 'x**2=4'
        assert sorted(solutions) == [-2, 2]

    def test_implicit_multiplication(self):
        # '2x' means 2*x
        assert calculate('2xS8') == ('2*x=8', [4])

    def test_invalid_equation_returns_none(self):
        formatted, result = calculate('xSS')
        assert result is None


class TestEditFlow:
    def test_substitute_maps_glyphs(self):
        assert substitute('8t3') == '8+3'
        assert substitute('xt2S5') == 'x+2=5'

    def test_solve_text_does_not_resubstitute(self):
        # 't' in already-edited text stays literal, it is not turned into '+'
        formatted, solution = solve_text('8+3')
        assert formatted == '8+3'
        assert solution == 11

    def test_solve_text_equation(self):
        assert solve_text('x2=4') == ('x**2=4', [-2, 2])


class TestHelpers:
    def test_evaluate_expression(self):
        assert evaluate_expression('2+3*4') == 14
        assert evaluate_expression('7/2') == pytest.approx(3.5)
        assert evaluate_expression('not math') is None

    def test_solve_equation(self):
        assert solve_equation('x+1=3') == [2]
        assert solve_equation('garbage') is None
