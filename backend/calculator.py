from sympy import solve
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    convert_xor,
)

# parse '^' as exponentiation instead of XOR
TRANSFORMATIONS = standard_transformations + (convert_xor,)

# common CNN misclassifications mapped to the intended symbol
SUBSTITUTIONS = {
    'D': '0',
    'G': '6',
    'b': '6',
    'B': '8',
    'Z': '2',
    'S': '=',
    't': '+',
    'f': '7',
    'M': '-',
    'W': '-',
    'L': '/',
    'g': '9',
}


def _parse(expression):
    return parse_expr(expression, transformations=TRANSFORMATIONS)


def evaluate_expression(expression):
    """Safely evaluate an arithmetic expression via sympy (no Python eval)."""
    try:
        result = _parse(expression)
        return int(result) if result.is_Integer else float(result)
    except Exception:
        print("invalid expression:", expression)
        return None


def solve_equation(equation):
    """Solve an equation of the form lhs = rhs with sympy."""
    try:
        lhs, rhs = equation.split("=", 1)
        return solve(_parse(lhs) - _parse(rhs))
    except Exception:
        print("invalid equation:", equation)
        return None


def _insert_implicit_operators(operation):
    """Turn '2x' into '2*x' and 'x2' into 'x**2' so sympy can parse it."""
    string, head = '', None
    for k in operation:
        if head is None:
            string += k
        elif k in '+-*/%^=' or head in '+-*/%^=':
            string += k
        elif k.isnumeric() and not head.isnumeric():
            string += '**' + k
        elif not k.isnumeric() and head.isnumeric():
            string += '*' + k
        else:
            string += k
        head = k
    return string


def calculate(operation):
    """Return (formatted_expression, solution) for a recognized string."""
    string = str(operation)
    for wrong, right in SUBSTITUTIONS.items():
        string = string.replace(wrong, right)

    if '=' not in string:
        string = string.replace('x', '*').replace('X', '*')
        return string, evaluate_expression(string)

    string = _insert_implicit_operators(string)
    return string, solve_equation(string)
