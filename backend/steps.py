"""Step-by-step working for equations in one variable.

Every step is computed by SymPy from the parsed equation, never guessed, so
the working always agrees with the answer. Covered:

- linear equations: clear fractions, expand, collect terms, divide
- quadratics: factor when the roots are rational, otherwise the quadratic
  formula with its discriminant
- equations whose variable cancels: always true, or never true

Anything else (several variables, higher degree, a variable under a root or
in a denominator) gets no steps; the answer alone is still shown.
"""
from sympy import Add, Poly, PolynomialError, expand, factor, factor_list, fraction, latex, lcm, solve

MAX_STEPS_DEGREE = 2


def _step(title, tex):
    return {'title': title, 'latex': tex}


def _eq(left, right):
    return f'{latex(left)} = {latex(right)}'


def _roots_text(var, roots):
    return f'{latex(var)} = ' + ', '.join(latex(r) for r in roots)


def _linear(poly, var, current):
    a, b = poly.all_coeffs()  # a*var + b = 0
    if a < 0:
        a, b = -a, -b  # keep the variable's coefficient positive
    steps = []
    collected = _eq(a * var, -b)
    if collected != current:
        steps.append(_step(f'Move the {var} terms to one side and the numbers to the other',
                           collected))
    if a != 1:
        steps.append(_step(f'Divide both sides by {latex(a)}', _eq(var, -b / a)))
    return steps


def _quadratic(poly, var, current):
    if poly.LC() < 0:
        poly = -poly  # a positive leading coefficient reads more naturally
    a, b, c = poly.all_coeffs()
    expr = poly.as_expr()
    steps = []
    standard = f'{latex(expr)} = 0'
    if standard != current:
        steps.append(_step('Bring everything to one side', standard))
    roots = solve(expr, var)

    _, factors = factor_list(expr)
    linear_factors = [f for f, _ in factors if Poly(f, var).degree() == 1]
    if linear_factors and all(Poly(f, var).degree() <= 1 for f, _ in factors):
        steps.append(_step('Factor', f'{latex(factor(expr))} = 0'))
        steps.append(_step('Set each factor equal to zero',
                           r',\quad '.join(f'{latex(f)} = 0' for f in linear_factors)))
        steps.append(_step('Solve each one', _roots_text(var, roots)))
        return steps

    disc = b ** 2 - 4 * a * c
    steps.append(_step('Use the quadratic formula',
                       rf'{latex(var)} = \frac{{-b \pm \sqrt{{b^2 - 4ac}}}}{{2a}}'
                       rf' \quad (a = {latex(a)},\ b = {latex(b)},\ c = {latex(c)})'))
    note = ', which is negative, so the roots are complex' if disc.is_negative else ''
    steps.append(_step(f'Work out the discriminant{note}',
                       rf'b^2 - 4ac = {latex(disc)}'))
    steps.append(_step('Substitute and simplify',
                       rf'{latex(var)} = \frac{{{latex(-b)} \pm \sqrt{{{latex(disc)}}}}}{{{latex(2 * a)}}}'
                       rf' \;\Rightarrow\; ' + _roots_text(var, roots)))
    return steps


def equation_steps(lhs, rhs, written_latex):
    """Steps (each {'title', 'latex'}) for solving lhs = rhs, or [] when the
    equation is outside what this module explains."""
    # symbols as written, so x+1 = x+2 still counts as an equation in x
    symbols = lhs.free_symbols | rhs.free_symbols
    if len(symbols) != 1:
        return []
    var = next(iter(symbols))
    steps = [_step('Start with the equation', written_latex)]

    # clear fractions with the least common multiple of the denominators
    terms = Add.make_args(expand(lhs)) + Add.make_args(expand(rhs))
    denominators = [fraction(t)[1] for t in terms]
    if any(d.has(var) for d in denominators):
        return []  # a variable in a denominator is a rational equation
    den = lcm(denominators) if denominators else 1
    if den != 1:
        left, right = expand(lhs * den), expand(rhs * den)
        steps.append(_step(f'Multiply both sides by {latex(den)} to clear the fractions',
                           _eq(left, right)))
    else:
        left, right = expand(lhs), expand(rhs)
        # SymPy keeps 3(x+1) as written, so a change here means there were
        # brackets to multiply out
        if left != lhs or right != rhs:
            steps.append(_step('Expand and simplify both sides', _eq(left, right)))

    try:
        poly = Poly(expand(left - right), var)
    except PolynomialError:
        return []
    degree = poly.degree()

    if poly.is_zero:
        steps.append(_step(f'The {var} terms cancel, leaving', '0 = 0'))
        steps.append(_step(f'This is true for every value of {var}', r'\text{true for every value}'))
        return steps
    if degree == 0:
        steps.append(_step(f'The {var} terms cancel, leaving', f'{latex(poly.as_expr())} = 0'))
        steps.append(_step('That is never true, so there is no solution', r'\text{no solution}'))
        return steps
    current = _eq(left, right)
    if degree == 1:
        return steps + _linear(poly, var, current)
    if degree == MAX_STEPS_DEGREE:
        return steps + _quadratic(poly, var, current)
    return []
