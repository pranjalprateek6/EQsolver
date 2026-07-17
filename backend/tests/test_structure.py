"""Spatial-parser tests. Tokens are built with explicit bounding boxes so we
can exercise 2D layout (superscripts, fractions, roots) without a model."""
from sympy.parsing.sympy_parser import parse_expr

from structure import build_expression


def tok(char, x, y, w, h):
    return {'char': char, 'x': x, 'y': y, 'w': w, 'h': h}


# main baseline symbols: height 40, top at y=100 (centre 120)
def base(char, x, w=28):
    return tok(char, x, 100, w, 40)


# raised exponent: smaller, higher (centre ~92)
def sup(char, x, w=16):
    return tok(char, x, 80, w, 24)


class TestBaseline:
    def test_simple_sum(self):
        assert build_expression([base('2', 0), base('+', 40), base('3', 80)]) == '2+3'

    def test_multi_digit_number(self):
        assert build_expression([base('1', 0), base('2', 30), base('+', 70), base('3', 110)]) == '12+3'

    def test_implicit_multiplication(self):
        assert build_expression([base('2', 0), base('x', 40)]) == '2*x'

    def test_minus_is_not_a_fraction(self):
        assert build_expression([base('6', 0), base('-', 40), base('2', 80)]) == '6-2'


class TestSuperscripts:
    def test_square(self):
        assert build_expression([base('x', 0), sup('2', 34)]) == 'x**(2)'

    def test_multi_digit_exponent(self):
        expr = build_expression([base('2', 0), sup('1', 34), sup('0', 52)])
        assert expr == '2**(10)'

    def test_power_of_group(self):
        tokens = [
            base('(', 0), base('x', 30), base('+', 60), base('1', 90), base(')', 120),
            sup('2', 152),
        ]
        assert build_expression(tokens) == '(x+1)**(2)'

    def test_polynomial(self):
        tokens = [
            base('x', 0), sup('2', 34),
            base('+', 60), base('2', 90), base('x', 120),
            base('+', 150), base('1', 180),
        ]
        assert build_expression(tokens) == 'x**(2)+2*x+1'


class TestFractions:
    def test_simple_fraction(self):
        tokens = [
            tok('1', 15, 60, 20, 34),
            tok('-', 0, 100, 70, 4),   # wide bar
            tok('2', 15, 110, 20, 34),
        ]
        assert build_expression(tokens) == '((1)/(2))'

    def test_algebraic_fraction(self):
        num = [tok('(', 0, 55, 22, 30), tok('x', 26, 55, 22, 30),
               tok('+', 52, 55, 22, 30), tok('1', 78, 55, 22, 30),
               tok(')', 104, 55, 22, 30)]
        den = [tok('(', 0, 115, 22, 30), tok('x', 26, 115, 22, 30),
               tok('-', 52, 115, 22, 30), tok('2', 78, 115, 22, 30),
               tok(')', 104, 115, 22, 30)]
        bar = [tok('-', 0, 100, 160, 4)]
        expr = build_expression(num + bar + den)
        assert expr == '(((x+1))/((x-2)))'
        # and it is valid to SymPy
        assert parse_expr(expr) is not None


class TestRoots:
    def test_sqrt_of_group(self):
        tokens = [
            tok('sqrt', 0, 90, 30, 50),
            base('x', 34), base('+', 66), base('1', 98),
        ]
        assert build_expression(tokens) == 'sqrt(x+1)'

    def test_sqrt_of_number(self):
        tokens = [tok('sqrt', 0, 90, 30, 50), base('9', 34)]
        assert build_expression(tokens) == 'sqrt(9)'


class TestNesting:
    def test_power_inside_fraction(self):
        num = [tok('x', 15, 55, 24, 34), tok('2', 42, 40, 14, 20)]  # x squared
        bar = [tok('-', 0, 100, 70, 4)]
        den = [tok('3', 15, 110, 24, 34)]
        expr = build_expression(num + bar + den)
        assert expr == '((x**(2))/(3))'
        assert parse_expr(expr) is not None
