from sympy import solve

import safe_parse
from safe_parse import ParseError, parse


def evaluate_expression(expression):
    """Evaluate an arithmetic expression (parsed safely, never eval'd)."""
    try:
        result, rhs = parse(expression)
        if rhs is not None:
            return None
        return int(result) if result.is_Integer else float(result)
    except (ParseError, TypeError, ValueError, ZeroDivisionError):
        return None


def solve_equation(equation):
    """Solve an equation 'lhs = rhs' with sympy, returning a list of roots."""
    try:
        lhs, rhs = parse(equation)
        if rhs is None:
            return None
        return solve(lhs - rhs)
    except (ParseError, TypeError, ValueError, NotImplementedError):
        return None


def to_latex(expression):
    """Render an explicit expression as LaTeX for display, or '' if it will
    not parse. It is kept as written, so '8+3' shows as 8 + 3 rather than its
    value. Equations are rendered as 'lhs = rhs'."""
    try:
        return safe_parse.to_latex(normalize(expression))
    except ParseError:
        return ''


def normalize(expression):
    # accept the human operators too, so typed '×'/'÷' solve like '*'/'/'
    return str(expression).strip().replace('×', '*').replace('÷', '/')


def solve_expression(expression):
    """Solve an already-explicit expression produced by the spatial parser
    (or edited by the user). Handles both plain arithmetic and equations.

    Returns (expression, solution); solution is a number, a list of roots, or
    None if it could not be parsed.
    """
    expression = normalize(expression)
    if not expression:
        return expression, None
    if '=' in expression:
        return expression, solve_equation(expression)
    return expression, evaluate_expression(expression)


def solve_job(expression):
    """Everything one request needs, as plain picklable data. This is what the
    sandboxed solver process runs (see sandbox.py)."""
    expression, solution = solve_expression(expression)
    return {
        'expression': expression,
        'solution': None if solution is None else str(solution),
        'latex': to_latex(expression),
    }
