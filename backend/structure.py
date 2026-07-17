"""Turn recognized characters with their positions into a parseable expression.

The classifier gives us a flat list of symbols, but real math is 2D: a small
digit sitting high and to the right of an ``x`` is an exponent, a wide
horizontal bar with symbols above and below is a fraction, and a radical sign
covers everything under it. This module reads that spatial layout and emits a
fully explicit, SymPy-ready string (``**`` for powers, explicit ``*``,
``/`` for fractions, ``sqrt(...)`` for roots).

A token is a dict: {'char': str, 'x': int, 'y': int, 'w': int, 'h': int},
where (x, y) is the top-left of its bounding box in image coordinates
(y grows downward).
"""
from statistics import median

# a horizontal bar this many times wider than the median symbol height is
# treated as a fraction bar rather than a minus sign
FRAC_BAR_WIDTH_FACTOR = 1.6
# a symbol whose vertical centre sits this fraction of the base height above
# the base's centre is treated as a superscript (exponent)
SUPERSCRIPT_OFFSET = 0.28
# horizontal gap (in median heights) that ends a square-root's radicand
RADICAND_GAP = 1.1

SQRT_CHARS = {'sqrt', '√'}
OPERATORS = set('+-*/=%')
# recognized math symbols -> their SymPy operator form
NORMALIZE = {'×': '*', '÷': '/'}


def _cx(t):
    return t['x'] + t['w'] / 2


def _cy(t):
    return t['y'] + t['h'] / 2


def _right(t):
    return t['x'] + t['w']


def _bottom(t):
    return t['y'] + t['h']


def _bbox(tokens):
    x = min(t['x'] for t in tokens)
    y = min(t['y'] for t in tokens)
    w = max(_right(t) for t in tokens) - x
    h = max(_bottom(t) for t in tokens) - y
    return {'x': x, 'y': y, 'w': w, 'h': h}


def _median_height(tokens):
    heights = [t['h'] for t in tokens if t['char'] not in ('-',) or t['h'] > 0]
    plain = [t['h'] for t in tokens]
    return median(plain) if plain else 1


def _overlaps_x(inner, bar):
    """True if inner's horizontal centre falls within the bar's span."""
    return bar['x'] <= _cx(inner) <= _right(bar)


def _is_frac_bar(t, median_h):
    return t['char'] == '-' and t['w'] >= FRAC_BAR_WIDTH_FACTOR * median_h


def _text(item):
    return item['expr'] if 'expr' in item else item['char']


def _collect_radicand(sqrt_tok, tokens, consumed, median_h):
    """Greedily take symbols to the right of a radical, within its vertical
    band, stopping at a wide horizontal gap."""
    band_top = sqrt_tok['y'] - 0.3 * median_h
    band_bottom = _bottom(sqrt_tok) + 0.3 * median_h
    candidates = sorted(
        (t for t in tokens
         if id(t) not in consumed and t is not sqrt_tok and _cx(t) > sqrt_tok['x']
         and band_top <= _cy(t) <= band_bottom),
        key=lambda t: t['x'],
    )
    radicand = []
    cursor = _right(sqrt_tok)
    for t in candidates:
        if t['x'] - cursor > RADICAND_GAP * median_h:
            break
        radicand.append(t)
        cursor = _right(t)
    return radicand


def _resolve_structures(tokens, median_h):
    """Fold fractions and roots into virtual items so the remaining pass only
    has to walk a single baseline. Returns items sorted left to right."""
    consumed = set()
    items = []

    # widest bars first so the outermost fraction wins when they nest
    for bar in sorted((t for t in tokens if _is_frac_bar(t, median_h)),
                      key=lambda t: -t['w']):
        if id(bar) in consumed:
            continue
        above = [t for t in tokens if id(t) not in consumed and t is not bar
                 and _overlaps_x(t, bar) and _cy(t) < bar['y']]
        below = [t for t in tokens if id(t) not in consumed and t is not bar
                 and _overlaps_x(t, bar) and _cy(t) > _bottom(bar)]
        if not above or not below:
            continue  # a lone long dash is just a minus, not a fraction
        for t in above + below:
            consumed.add(id(t))
        consumed.add(id(bar))
        num = build_expression(above)
        den = build_expression(below)
        items.append({'expr': f'(({num})/({den}))', **_bbox([bar] + above + below)})

    for tok in sorted(tokens, key=lambda t: t['x']):
        if id(tok) in consumed or tok['char'] not in SQRT_CHARS:
            continue
        radicand = _collect_radicand(tok, tokens, consumed, median_h)
        for t in radicand:
            consumed.add(id(t))
        consumed.add(id(tok))
        inside = build_expression(radicand) if radicand else ''
        items.append({'expr': f'sqrt({inside})', **_bbox([tok] + radicand)})

    for tok in tokens:
        if id(tok) not in consumed:
            items.append(tok)
            consumed.add(id(tok))

    return sorted(items, key=lambda it: it['x'])


def _needs_multiply(left, right):
    """Insert '*' between two adjacent baseline units when juxtaposition means
    multiplication (2x, x(, )(, )2) but not when it forms a number (12, 3.5)."""
    a = left[-1]
    b = right[0]
    if a in OPERATORS or a in '(^':
        return False
    if b in OPERATORS or b in ')^':
        return False
    if a.isdigit() and (b.isdigit() or b == '.'):
        return False
    if a == '.' or b == '.':
        return False
    return True


def _is_superscript(base, other):
    """other is an exponent of base if it sits clearly higher and to the right."""
    return _cx(other) > _cx(base) and _cy(other) < _cy(base) - SUPERSCRIPT_OFFSET * base['h']


def _combine(items):
    """Walk baseline items left to right, raising superscript groups."""
    if not items:
        return ''
    out = ''
    i = 0
    n = len(items)
    while i < n:
        base = items[i]
        piece = _text(base)
        if out and _needs_multiply(out, piece):
            out += '*'
        out += piece

        # gather any following items that are raised relative to this base
        group = []
        j = i + 1
        while j < n and _is_superscript(base, items[j]):
            group.append(items[j])
            j += 1
        if group:
            out += '**(' + _combine(group) + ')'
            i = j
        else:
            i += 1
    return out


def build_expression(tokens):
    """Return a SymPy-ready string for a list of positioned character tokens."""
    if not tokens:
        return ''
    # normalize display symbols (×, ÷) to their operator form up front
    tokens = [{**t, 'char': NORMALIZE.get(t['char'], t['char'])} for t in tokens]
    median_h = _median_height(tokens)
    items = _resolve_structures(tokens, median_h)
    return _combine(items)
