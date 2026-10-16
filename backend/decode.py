"""Choose among the classifier's top guesses using the equation as context.

The classifier reads each glyph alone, so it cannot know that the tall
thing between two numbers is more likely a times sign than the letter x, or
that a raised symbol after a variable is more likely the digit 2 than the
letter z. This module scores whole readings instead of single glyphs:

    score = sum(log p(guess)) + penalties for readings that make no sense

and keeps the best one. Readings are generated best-first from each glyph's
top-k guesses, so the greedy reading is always considered and only a few
dozen alternatives are ever checked. Everything here is cheap: the spatial
parser and the allowlisted parser, never SymPy's solver.

Stroke geometry from the segmenter is treated as a hard fact: a single wide
bar can only be a minus (or fraction bar), and two merged bars only an '='.
"""

import heapq
import math
import re
from itertools import pairwise

from safe_parse import ParseError, parse_tree
from structure import build_expression

VARIABLES = set('xyz')
DIGITS = set('0123456789')

# how many whole readings to score at most
MAX_READINGS = 64
# a guess below this probability is never worth considering
MIN_PROB = 1e-3
# log-space penalties (e^-2 ~ 0.14: a penalty of 2 lets a guess about 7x
# less likely win if it removes the problem)
UNPARSEABLE = 25.0
UNSOLVABLE = 2.0  # variables but no '=': nothing to solve for
VARIABLE_IN_EXPONENT = 2.0
VARIABLE_THEN_DIGIT = 2.0  # 'x3' is almost always '×3' or a misread


def _with_shape_facts(tokens):
    """Force what the stroke geometry already decides."""
    fixed = []
    for t in tokens:
        shape = t.get('shape')
        if shape == 'bar':
            t = {**t, 'alternatives': [('-', 1.0)]}
        elif shape == 'equals':
            t = {**t, 'alternatives': [('=', 1.0)]}
        fixed.append(t)
    return fixed


def _candidates(token):
    alts = [
        (c, p)
        for c, p in token.get('alternatives') or [(token['char'], token['confidence'])]
        if p >= MIN_PROB
    ]
    return alts or [(token['char'], max(token['confidence'], MIN_PROB))]


def _readings(options):
    """Yield (log_prob, choice_indices) best-first over independent choices."""
    logs = [[math.log(max(p, MIN_PROB)) for _, p in opts] for opts in options]
    start = tuple(0 for _ in options)
    heap = [(-sum(lp[0] for lp in logs), start)]
    seen = {start}
    while heap:
        neg, picks = heapq.heappop(heap)
        yield -neg, picks
        for i, k in enumerate(picks):
            if k + 1 < len(options[i]):
                nxt = picks[:i] + (k + 1,) + picks[i + 1 :]
                if nxt not in seen:
                    seen.add(nxt)
                    heapq.heappush(heap, (neg - logs[i][k + 1] + logs[i][k], nxt))


def _centre_y(t):
    return t['y'] + t['h'] / 2


def _penalty(tokens, expression):
    try:
        lhs, rhs = parse_tree(expression)
    except ParseError:
        return UNPARSEABLE
    penalty = 0.0
    chars = {t['char'] for t in tokens}
    if rhs is None and chars & VARIABLES:
        penalty += UNSOLVABLE
    if re.search(r'\*\*\([^)]*[xyz]', expression):
        penalty += VARIABLE_IN_EXPONENT
    ordered = sorted(tokens, key=lambda t: t['x'])
    for a, b in pairwise(ordered):
        same_line = abs(_centre_y(a) - _centre_y(b)) < 0.25 * max(a['h'], b['h'])
        if a['char'] in VARIABLES and b['char'] in DIGITS and same_line:
            penalty += VARIABLE_THEN_DIGIT
    return penalty


def choose(tokens):
    """Return the tokens with each 'char' (and 'confidence') set to the best
    whole reading. 'alternatives' is kept so the UI can offer the others."""
    if not tokens:
        return tokens
    tokens = _with_shape_facts(tokens)
    options = [_candidates(t) for t in tokens]

    best = None
    for n, (log_prob, picks) in enumerate(_readings(options)):
        if n >= MAX_READINGS or (best and log_prob <= best[0]):
            # readings come best-first by probability, so once even a
            # penalty-free one cannot beat the best score, stop
            break
        reading = [
            {**t, 'char': options[i][k][0], 'confidence': round(options[i][k][1], 4)}
            for i, (t, k) in enumerate(zip(tokens, picks, strict=True))
        ]
        score = log_prob - _penalty(reading, build_expression(reading))
        if best is None or score > best[0]:
            best = (score, reading)
    return best[1]
