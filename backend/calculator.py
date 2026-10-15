from sympy import N, latex, solve

import safe_parse
from safe_parse import ParseError, parse

# significant digits shown for an approximate (irrational) value
APPROX_DIGITS = 6
ALL_VALUES = 'all values'


def _number(value):
    """A plain Python number for an evaluated expression, or None if it is not
    a real number (it still has variables in it, is complex, or divides by 0)."""
    if not value.is_number or not value.is_finite or not value.is_real:
        return None
    return int(value) if value.is_Integer else float(value)


def evaluate_expression(expression):
    """Evaluate an arithmetic expression (parsed safely, never eval'd)."""
    try:
        result, rhs = parse(expression)
    except ParseError:
        return None
    if rhs is not None:
        return None
    try:
        return _number(result)
    except (TypeError, ValueError, OverflowError):
        return None


def _solve_parsed(lhs, rhs):
    difference = lhs - rhs
    if difference.expand() == 0:
        return ALL_VALUES
    return solve(difference)


def solve_equation(equation):
    """Solve an equation 'lhs = rhs' with sympy, returning a list of roots
    (empty if there is none), or ALL_VALUES when it holds for every value."""
    try:
        lhs, rhs = parse(equation)
        if rhs is None:
            return None
        return _solve_parsed(lhs, rhs)
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

    Returns (expression, solution); solution is a number, a list of roots,
    ALL_VALUES, or None if it could not be parsed or solved.
    """
    expression = normalize(expression)
    if not expression:
        return expression, None
    if '=' in expression:
        return expression, solve_equation(expression)
    return expression, evaluate_expression(expression)


def _value_latex(value):
    """Exact value, plus a decimal when the exact form is not already one:
    1/2 shows as \\frac{1}{2} = 0.5 and sqrt(2) as \\sqrt{2} \\approx 1.41421."""
    exact = latex(value)
    if value.is_Integer or not value.is_number:
        return exact
    if value.is_Rational:
        return f'{exact} = {_decimal(value)}'
    if value.is_real:
        return f'{exact} \\approx {_decimal(N(value, APPROX_DIGITS))}'
    return exact


def _decimal(value):
    return f'{float(value):.{APPROX_DIGITS}g}'


def _roots_latex(roots, lhs, rhs):
    if roots == ALL_VALUES:
        return '\\text{true for every value}'
    if not roots:
        return '\\text{no solution}'
    if isinstance(roots[0], dict):
        # several variables: each solution expresses some of them in terms
        # of the others, e.g. x = y - z
        return ',\\quad '.join(
            ', '.join(f'{latex(var)} = {latex(val)}' for var, val in sol.items())
            for sol in roots)
    symbols = sorted((lhs - rhs).free_symbols, key=lambda s: s.name)
    values = ', '.join(_value_latex(r) if len(roots) == 1 else latex(r) for r in roots)
    if len(symbols) == 1:
        return f'{latex(symbols[0])} = {values}'
    return values


def solve_job(expression):
    """Everything one request needs, as plain picklable data. This is what the
    sandboxed solver process runs (see sandbox.py). Parses and solves once."""
    expression = normalize(expression)
    result = {'expression': expression, 'solution': None, 'solution_latex': '',
              'latex': to_latex(expression)}
    try:
        lhs, rhs = parse(expression)
        if rhs is None:
            value = _number(lhs)
            if value is not None:
                result['solution'] = str(value)
                result['solution_latex'] = _value_latex(lhs)
        else:
            roots = _solve_parsed(lhs, rhs)
            result['solution'] = str(roots)
            result['solution_latex'] = _roots_latex(roots, lhs, rhs)
    except (ParseError, TypeError, ValueError, NotImplementedError, OverflowError):
        pass
    return result
