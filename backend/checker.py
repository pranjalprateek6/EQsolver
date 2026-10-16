"""Check a student's working: does each line keep the solutions of the last?

A student writes one equation per line (``2x+3=11``, ``2x=8``, ``x=4``). Two
consecutive lines are a correct step when they have the same solution set.
The first line that changes it is flagged, with a short hint when the change
matches a common slip:

- a sign error when moving a term across the ``=``
- multiplying or dividing only one side
- losing a solution (dividing by the variable, a square root without ±)
- gaining one (squaring both sides, multiplying by the variable)

Hints are deterministic and conservative: each is reported only when the
line matches that slip exactly, otherwise the line gets a generic note. They
never contain a solution, so checking work does not hand out the answer;
``reveal`` asks for it explicitly.

Solutions are taken over the real numbers, the way students solve, so
``x**3 = 8`` and ``x = 2`` count as the same. Lines without ``=`` are checked
as an expression being simplified: each must equal the one before.

Every input goes through the allowlisted parser (safe_parse), never eval. This
runs inside the sandbox (see sandbox.py), which enforces the time limit.
"""
import re

from sympy import (Add, Complement, Dummy, EmptySet, FiniteSet, Interval, S, Union, cancel,
                   expand, latex, simplify, solveset, together)

import calculator
from safe_parse import ParseError, parse, to_latex

MAX_LINES = 12

UNREADABLE = 'this line could not be read as an equation'
MIXED = 'write every line as an equation (with =), or every line without one'
UNCHECKED = 'this line could not be checked'
DIFFERENT = 'this line has different solutions than the one before'
NOT_EQUAL = 'this is not equal to the line before'

_CHECK_ERRORS = (TypeError, ValueError, NotImplementedError, AttributeError,
                 RecursionError, OverflowError, ZeroDivisionError)


def _parse_line(text):
    text = calculator.normalize(text)
    try:
        lhs, rhs = parse(text)
        return text, to_latex(text), (lhs, rhs)
    except (ParseError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return text, '', None


def _number_ratio(a, b):
    """a / b when it is a nonzero number, else None."""
    if b == 0:
        return None
    ratio = cancel(together(a / b))
    if ratio.is_number and ratio.is_finite and ratio != 0:
        return ratio
    return None


def _same_points(a, b):
    if len(a) != len(b):
        return False
    return all(any(simplify(p - q) == 0 for q in b) for p in a)


def _contains_points(big, small):
    return all(any(simplify(p - q) == 0 for q in big) for p in small)


def _solution_set(equation, var):
    lhs, rhs = equation
    return solveset(lhs - rhs, var, domain=S.Reals)


def _same_sets(a, b):
    """True / False when the two solution sets can be compared, else None."""
    if isinstance(a, FiniteSet) and isinstance(b, FiniteSet):
        return _same_points(a, b)
    if a == b:
        return True
    try:
        empty = (a - b) == EmptySet and (b - a) == EmptySet
    except _CHECK_ERRORS:
        return None
    if empty:
        return True
    # a symbolic set (a condition SymPy could not solve) proves nothing
    return False if _concrete(a) and _concrete(b) else None


def _concrete(s):
    """Points, intervals and their unions: sets whose equality is decided."""
    if isinstance(s, (FiniteSet, Interval)) or s == EmptySet:
        return not s.free_symbols
    if isinstance(s, (Union, Complement)):
        return all(_concrete(arg) for arg in s.args)
    return False


def _proportional(prev, cur):
    """Both lines rearrange to the same equation up to a constant factor:
    an exact test that needs no solving, for several variables too."""
    (l1, r1), (l2, r2) = prev, cur
    return _number_ratio(expand(l1 - r1), expand(l2 - r2)) is not None


def _sign_error(prev, cur):
    """A term moved across the '=' without changing its sign: the line
    matches the previous one with that term's sign flipped on the move."""
    (l1, r1), (l2, r2) = prev, cur
    d1, d2 = expand(l1 - r1), expand(l2 - r2)
    moves = [(t, d1 - 2 * t) for t in Add.make_args(expand(l1))] + \
            [(t, d1 + 2 * t) for t in Add.make_args(expand(r1))]
    for term, wrong in moves:
        if term != 0 and expand(wrong) != 0 and _number_ratio(d2, wrong) is not None:
            return term
    return None


def _one_side(prev, cur):
    """Only one side was multiplied or divided: the other side is unchanged
    and the changed side is the old one times a constant. Returns a hint."""
    (l1, r1), (l2, r2) = prev, cur
    for new_l, new_r in ((l2, r2), (r2, l2)):  # the sides may be swapped
        for old, new, kept_old, kept_new, side in (
                (l1, new_l, r1, new_r, 'left'), (r1, new_r, l1, new_l, 'right')):
            if old == 0 or new == 0 or simplify(kept_old - kept_new) != 0:
                continue
            factor = _number_ratio(new, old)
            if factor is None or factor == 1:
                continue
            other = 'right' if side == 'left' else 'left'
            if factor == -1:
                return (f'it looks like you changed the sign of the {side} side only; '
                        f'do the same to the {other} side')
            if abs(factor) < 1:
                return (f'it looks like you divided only the {side} side by '
                        f'{_plain(1 / factor)}; divide the {other} side too')
            return (f'it looks like you multiplied only the {side} side by '
                    f'{_plain(factor)}; multiply the {other} side too')
    return None


def _plain(value):
    # 2*x -> 2x and x**2 -> x^2, the way the student wrote it
    return re.sub(r'(\d)\*(?=[a-z(])', r'\1', str(value).replace('**', '^'))


def _root_hint(a, b, var):
    if not (isinstance(a, FiniteSet) and isinstance(b, FiniteSet)):
        return None
    if len(b) < len(a) and _contains_points(a, b):
        return (f'this line lost a solution; dividing by something with {var} in it, '
                f'or taking a square root without ±, can drop one')
    if len(b) > len(a) and _contains_points(b, a):
        return (f'this line gained a solution that does not work in the line before; '
                f'squaring both sides or multiplying by something with {var} in it '
                f'can add one')
    return None


def _check_equations(prev, cur, var):
    """(ok, reason) for one step between two equations."""
    if _proportional(prev, cur):
        return True, ''
    same = None
    a = b = None
    if var is not None:
        a, b = _solution_set(prev, var), _solution_set(cur, var)
        same = _same_sets(a, b)
    if same:
        return True, ''
    if same is None and var is not None:
        return None, UNCHECKED
    hint = _one_side(prev, cur)
    if hint:
        return False, hint
    term = _sign_error(prev, cur)
    if term is not None:
        return False, (f'check the sign when you moved {_plain(term)} across the =: '
                       f'it should become {_plain(-term)} on the other side')
    if var is not None:
        hint = _root_hint(a, b, var)
        if hint:
            return False, hint
    if var is None:
        # several variables, and the lines are not rearrangements of each other
        return None, UNCHECKED
    return False, DIFFERENT


def _check_expressions(prev, cur):
    if simplify(prev - cur) == 0:
        return True, ''
    return False, NOT_EQUAL


def _variable(parsed):
    symbols = set()
    for lhs, rhs in parsed:
        symbols |= lhs.free_symbols | (rhs.free_symbols if rhs is not None else set())
    if len(symbols) == 1:
        return symbols.pop()
    if not symbols:
        return Dummy('x')  # plain arithmetic: each line is simply true or false
    return None


def _finished(equation):
    """The line reads 'x = number' (or 'number = x')."""
    lhs, rhs = equation
    return any(side.is_Symbol and other.is_number for side, other in ((lhs, rhs), (rhs, lhs)))


def check_lines(lines, reveal=False):
    """Check consecutive lines of working. Returns plain picklable data:

    {'lines': [{'text', 'latex', 'ok', 'reason'}], 'first_error': index or
    None, 'finished': bool, 'answer_latex': str (only when reveal is set)}.
    ``ok`` is True for a correct step, False for a wrong one, and None when
    the step could not be checked. The first line is the problem itself and
    is ok whenever it can be read.
    """
    rows = [_parse_line(text) for text in lines[:MAX_LINES]]
    readable = [p for _, _, p in rows if p is not None]
    has_eq = {rhs is not None for _, rhs in readable}
    mixed = len(has_eq) > 1
    equations = has_eq == {True}
    var = _variable(readable) if equations else None

    out = []
    prev = None
    for text, tex, parsed in rows:
        row = {'text': text, 'latex': tex, 'ok': True, 'reason': ''}
        if parsed is None:
            row.update(ok=False, reason=UNREADABLE)
        elif mixed:
            row.update(ok=False, reason=MIXED)
        elif prev is not None:
            try:
                if equations:
                    ok, reason = _check_equations(prev, parsed, var)
                else:
                    ok, reason = _check_expressions(prev[0], parsed[0])
            except _CHECK_ERRORS:
                ok, reason = None, UNCHECKED
            row.update(ok=ok, reason=reason)
        if parsed is not None:
            prev = parsed
        out.append(row)

    first_error = next((i for i, r in enumerate(out) if r['ok'] is False), None)
    last = rows[-1][2] if rows else None
    result = {
        'lines': out,
        'first_error': first_error,
        'finished': bool(equations and first_error is None and last is not None
                         and len(rows) > 1 and _finished(last)
                         and all(r['ok'] for r in out)),
    }
    if reveal:
        result['answer_latex'] = _answer(readable[0] if readable else None, equations)
    return result


def _answer(first, equations):
    if first is None:
        return ''
    lhs, rhs = first
    try:
        if not equations:
            return latex(simplify(lhs))
        return calculator._roots_latex(calculator._solve_parsed(lhs, rhs), lhs, rhs)
    except _CHECK_ERRORS:
        return ''


def check_job(payload):
    """The sandboxed entry point (see sandbox.py)."""
    return check_lines(payload.get('lines', []), reveal=bool(payload.get('reveal')))
