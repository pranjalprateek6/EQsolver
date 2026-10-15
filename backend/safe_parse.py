"""A small, allowlisted math parser that builds SymPy objects without eval.

SymPy's ``parse_expr`` runs ``eval`` on its input, so it must never see
user-supplied text. This module tokenizes the input against a fixed grammar
and constructs the SymPy tree directly, so the only things that can appear in
an expression are numbers, single-letter variables, ``pi``, ``sqrt`` and the
arithmetic operators.

Grammar (``^`` and ``**`` are both powers; juxtaposition multiplies, as in
``2x`` or ``3(x+1)``)::

    equation := expr ('=' expr)?
    expr     := term (('+' | '-') term)*
    term     := unary (('*' | '/') unary | <implicit> power)*
    unary    := ('+' | '-') unary | power
    power    := primary (('**' | '^') unary)?
    primary  := NUMBER | NAME | 'sqrt' '(' expr ')' | '(' expr ')'

Size limits keep a single request from tying up the server: the input length,
token count and nesting depth are capped, and a numeric power whose result
would be enormous (``9**9**9``) is rejected before SymPy computes it.
"""
import re

import sympy

MAX_LENGTH = 300
MAX_TOKENS = 300
MAX_DEPTH = 30
MAX_NUMBER_DIGITS = 30
# a numeric power is refused if its result would need more bits than this
# (about 10,000 decimal digits)
MAX_RESULT_BITS = 33_000

FUNCTIONS = {'sqrt'}
CONSTANTS = {'pi': sympy.pi}

_TOKEN_RE = re.compile(r"""
    (?P<number>\d+(?:\.\d+)?|\.\d+)
  | (?P<name>[a-z]+)
  | (?P<op>\*\*|[-+*/^=()])
  | (?P<space>\s+)
""", re.VERBOSE)


class ParseError(ValueError):
    """The input is not an allowed expression."""


def tokenize(text):
    if len(text) > MAX_LENGTH:
        raise ParseError(f'expression is too long (max {MAX_LENGTH} characters)')
    tokens = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if not match:
            raise ParseError(f'unexpected character {text[pos]!r}')
        pos = match.end()
        kind = match.lastgroup
        value = match.group()
        if kind == 'space':
            continue
        if kind == 'number' and len(value) > MAX_NUMBER_DIGITS:
            raise ParseError('number is too long')
        if kind == 'name' and value not in FUNCTIONS and value not in CONSTANTS \
                and len(value) != 1:
            raise ParseError(f'unknown name {value!r}')
        tokens.append((kind, value))
        if len(tokens) > MAX_TOKENS:
            raise ParseError('expression is too long')
    return tokens


class _Parser:
    """Recursive-descent parser producing a tiny AST of tuples."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        kind, tok = self.peek()
        if kind is None or (value is not None and tok != value):
            want = repr(value) if value else 'more input'
            raise ParseError(f'expected {want}')
        self.pos += 1
        return kind, tok

    def at_op(self, *values):
        kind, tok = self.peek()
        return kind == 'op' and tok in values

    def enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError('expression is nested too deeply')

    def leave(self):
        self.depth -= 1

    def equation(self):
        lhs = self.expr()
        rhs = None
        if self.at_op('='):
            self.take('=')
            rhs = self.expr()
        if self.pos != len(self.tokens):
            raise ParseError(f'unexpected {self.peek()[1]!r}')
        return lhs, rhs

    def expr(self):
        node = self.term()
        while self.at_op('+', '-'):
            _, op = self.take()
            node = ('add' if op == '+' else 'sub', node, self.term())
        return node

    def term(self):
        node = self.unary()
        while True:
            if self.at_op('*', '/'):
                _, op = self.take()
                node = ('mul' if op == '*' else 'div', node, self.unary())
            elif self._starts_implicit_factor():
                node = ('mul', node, self.power())
            else:
                return node

    def _starts_implicit_factor(self):
        # '2x', 'x(', ')(' and '2sqrt(' multiply; '2 3' is a typo, not 6
        kind, tok = self.peek()
        return kind == 'name' or (kind == 'op' and tok == '(')

    def unary(self):
        if self.at_op('+', '-'):
            _, op = self.take()
            self.enter()
            operand = self.unary()
            self.leave()
            return operand if op == '+' else ('neg', operand)
        return self.power()

    def power(self):
        base = self.primary()
        if self.at_op('**', '^'):
            self.take()
            self.enter()
            exponent = self.unary()
            self.leave()
            return ('pow', base, exponent)
        return base

    def primary(self):
        kind, tok = self.take()
        if kind == 'number':
            return ('num', tok)
        if kind == 'name':
            if tok in FUNCTIONS:
                self.take('(')
                inner = self._group()
                return (tok, inner)
            if tok in CONSTANTS:
                return ('const', tok)
            return ('sym', tok)
        if kind == 'op' and tok == '(':
            return self._group()
        raise ParseError(f'unexpected {tok!r}')

    def _group(self):
        self.enter()
        inner = self.expr()
        self.leave()
        self.take(')')
        return inner


def _bits(rational):
    return max(abs(rational.p).bit_length(), rational.q.bit_length(), 1)


def _safe_pow(base, exponent):
    if base.is_Rational and exponent.is_Rational:
        magnitude = abs(exponent.p) // exponent.q + 1
        if _bits(base) * magnitude > MAX_RESULT_BITS:
            raise ParseError('number is too large')
    return sympy.Pow(base, exponent)


def _build(node):
    kind = node[0]
    if kind == 'num':
        return sympy.Rational(node[1])
    if kind == 'sym':
        return sympy.Symbol(node[1])
    if kind == 'const':
        return CONSTANTS[node[1]]
    if kind == 'neg':
        return -_build(node[1])
    if kind == 'sqrt':
        return sympy.sqrt(_build(node[1]))

    left = _build(node[1])
    right = _build(node[2])
    if kind == 'add':
        return left + right
    if kind == 'sub':
        return left - right
    if kind == 'mul':
        return left * right
    if kind == 'div':
        return left / right
    if kind == 'pow':
        return _safe_pow(left, right)
    raise ParseError(f'unknown node {kind!r}')


def parse_tree(text):
    """Parse ``text`` into ``(lhs, rhs)`` syntax trees; ``rhs`` is None when
    there is no ``=``. Raises ParseError for anything outside the grammar or
    the size limits."""
    tokens = tokenize(str(text).strip())
    if not tokens:
        raise ParseError('empty expression')
    return _Parser(tokens).equation()


def parse(text):
    """Parse ``text`` into ``(lhs, rhs)`` SymPy expressions; ``rhs`` is None
    when there is no ``=``. Raises ParseError like parse_tree."""
    lhs, rhs = parse_tree(text)
    return _build(lhs), None if rhs is None else _build(rhs)


# binding strength of each node, for deciding where LaTeX needs parentheses
_PRECEDENCE = {'add': 1, 'sub': 1, 'mul': 2, 'div': 2, 'neg': 3, 'pow': 4}


def _latex(node, parent=0):
    """LaTeX for a syntax tree, in the order the user wrote it (SymPy's own
    printer would reorder terms or show the evaluated value instead)."""
    kind = node[0]
    if kind == 'num':
        return node[1]
    if kind == 'sym':
        return node[1]
    if kind == 'const':
        return '\\' + node[1]
    if kind == 'sqrt':
        return '\\sqrt{' + _latex(node[1]) + '}'
    if kind == 'div':
        # a fraction is visually self-contained; it only needs parentheses
        # when raised to a power
        text = '\\frac{' + _latex(node[1]) + '}{' + _latex(node[2]) + '}'
        return _paren(text) if parent > _PRECEDENCE['pow'] else text

    prec = _PRECEDENCE[kind]
    if kind == 'neg':
        text = '-' + _latex(node[1], prec + 1)
    elif kind == 'pow':
        # the base binds tighter than anything but an atom; the exponent is
        # set in braces so it needs no parentheses of its own
        text = _latex(node[1], prec + 1) + '^{' + _latex(node[2]) + '}'
    elif kind == 'mul':
        left = _latex(node[1], prec)
        right = _latex(node[2], prec + 1)
        # digits next to digits must stay apart: 2 \cdot 3, but 2x and 2\sqrt{x}
        sep = ' \\cdot ' if right[:1].isdigit() or right[:1] == '-' else ' '
        text = left + sep + right
    else:  # add / sub: the right side of a '-' needs parentheses at equal rank
        op = ' + ' if kind == 'add' else ' - '
        right_prec = prec + 1 if kind == 'sub' else prec
        text = _latex(node[1], prec) + op + _latex(node[2], right_prec)
    return _paren(text) if prec < parent else text


def _paren(text):
    return '\\left(' + text + '\\right)'


def to_latex(text):
    """LaTeX for an expression or equation exactly as written. Raises
    ParseError like parse_tree."""
    lhs, rhs = parse_tree(text)
    if rhs is None:
        return _latex(lhs)
    return _latex(lhs) + ' = ' + _latex(rhs)
