"""The allowlisted parser: what it accepts, what it refuses, and that hostile
input is refused quickly instead of being evaluated."""
import time

import pytest
import sympy

from calculator import solve_expression, to_latex
from safe_parse import MAX_DEPTH, MAX_LENGTH, ParseError, parse

x = sympy.Symbol('x')


class TestAccepts:
    def test_arithmetic(self):
        assert parse('2+3*4') == (14, None)

    def test_equation_sides(self):
        lhs, rhs = parse('x**2=4')
        assert lhs == x**2 and rhs == 4

    def test_caret_is_power(self):
        assert parse('2^10')[0] == 1024

    def test_power_is_right_associative(self):
        assert parse('2**3**2')[0] == 512

    def test_unary_minus_binds_looser_than_power(self):
        assert parse('-2^2')[0] == -4

    def test_implicit_multiplication(self):
        assert parse('2x')[0] == 2 * x
        assert parse('3(x+1)')[0] == 3 * (x + 1)
        assert parse('(x+1)(x-1)')[0] == (x + 1) * (x - 1)

    def test_decimals_are_exact(self):
        assert parse('0.1+0.2')[0] == sympy.Rational(3, 10)

    def test_sqrt_and_pi(self):
        assert parse('sqrt(16)')[0] == 4
        assert parse('pi')[0] == sympy.pi


class TestRefuses:
    @pytest.mark.parametrize('text', [
        "__import__('os').system('echo pwned')",
        'x.__class__',
        "eval('1')",
        'lambda: 1',
        'factorial(10)',
        'exp(1)',
        '[1, 2]',
        'x; y',
        '1 if x else 2',
        'garbage',
    ])
    def test_code_and_unknown_names(self, text):
        with pytest.raises(ParseError):
            parse(text)

    @pytest.mark.parametrize('text', ['', '++', '2*', '(1+2', '1+2)', 'x=y=z', '2 3', '=4'])
    def test_malformed(self, text):
        with pytest.raises(ParseError):
            parse(text)

    def test_too_long(self):
        with pytest.raises(ParseError):
            parse('1+' * MAX_LENGTH + '1')

    def test_too_deep(self):
        with pytest.raises(ParseError):
            parse('(' * (MAX_DEPTH + 1) + '1' + ')' * (MAX_DEPTH + 1))

    def test_huge_number_literal(self):
        with pytest.raises(ParseError):
            parse('1' * 100)

    @pytest.mark.parametrize('text', ['9**9**9**9', '10**100000', '(10**1000)**1000', '1**(10**100)'])
    def test_power_towers_are_refused_without_computing(self, text):
        start = time.perf_counter()
        with pytest.raises(ParseError):
            parse(text)
        assert time.perf_counter() - start < 1

    def test_hostile_input_solves_to_none(self):
        assert solve_expression("__import__('os').system('echo')")[1] is None
        assert solve_expression('9**9**9**9')[1] is None


class TestLatex:
    def test_kept_as_written_not_evaluated(self):
        assert to_latex('8+3') == '8 + 3'

    def test_equation(self):
        assert to_latex('x**2-5*x+6=0') == 'x^{2} - 5 x + 6 = 0'

    def test_fraction(self):
        assert to_latex('((1)/(2))') == '\\frac{1}{2}'

    def test_parentheses_only_where_needed(self):
        assert to_latex('2*(3-(4-5))') == '2 \\left(3 - \\left(4 - 5\\right)\\right)'
        assert to_latex('(-2)^2') == '\\left(-2\\right)^{2}'

    def test_digits_are_separated(self):
        assert to_latex('2*3') == '2 \\cdot 3'

    def test_invalid_is_empty(self):
        assert to_latex('++') == ''
