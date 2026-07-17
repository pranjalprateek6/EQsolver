from sympy import latex, solve
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    convert_xor,
)

# parse '^' as exponentiation instead of XOR (harmless; the parser emits '**')
TRANSFORMATIONS = standard_transformations + (convert_xor,)


def _parse(expression):
    return parse_expr(expression, transformations=TRANSFORMATIONS)


def evaluate_expression(expression):
    """Evaluate an arithmetic expression via sympy (no Python eval)."""
    try:
        result = _parse(expression)
        return int(result) if result.is_Integer else float(result)
    except Exception:
        return None


def solve_equation(equation):
    """Solve an equation 'lhs = rhs' with sympy, returning a list of roots."""
    try:
        lhs, rhs = equation.split("=", 1)
        return solve(_parse(lhs) - _parse(rhs))
    except Exception:
        return None


def to_latex(expression):
    """Render an explicit expression as LaTeX for display, or '' if it will
    not parse. Equations are rendered as 'lhs = rhs'."""
    expression = str(expression).strip()
    try:
        if '=' in expression:
            lhs, rhs = expression.split('=', 1)
            return latex(_parse(lhs)) + ' = ' + latex(_parse(rhs))
        return latex(_parse(expression))
    except Exception:
        return ''


def solve_expression(expression):
    """Solve an already-explicit expression produced by the spatial parser
    (or edited by the user). Handles both plain arithmetic and equations.

    Returns (expression, solution); solution is a number, a list of roots, or
    None if it could not be parsed. Unlike the old Level 1 path this does no
    symbol substitution or implicit-operator insertion: the input is already
    explicit (** for powers, sqrt(), *, /).
    """
    expression = str(expression).strip()
    if not expression:
        return expression, None
    if '=' in expression:
        return expression, solve_equation(expression)
    return expression, evaluate_expression(expression)
