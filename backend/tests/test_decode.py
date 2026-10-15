"""Context decoder: picks the reading that makes sense as a whole equation,
and trusts stroke geometry over the classifier."""
from decode import choose
from structure import build_expression


def tok(alts, x, y=100, w=28, h=40, shape=None):
    return {'char': alts[0][0], 'confidence': alts[0][1], 'alternatives': alts,
            'x': x, 'y': y, 'w': w, 'h': h, 'shape': shape}


def read(tokens):
    return build_expression(choose(tokens))


def test_confident_reading_is_kept():
    tokens = [tok([('2', 0.99)], 0), tok([('+', 0.98), ('x', 0.02)], 40), tok([('3', 0.99)], 80)]
    assert read(tokens) == '2+3'


def test_times_preferred_over_variable_between_numbers():
    # the classifier slightly prefers 'x', but '2x3' would mean 2*x*3 with
    # nothing to solve; '2×3' is the sensible reading
    tokens = [tok([('2', 0.99)], 0), tok([('x', 0.55), ('×', 0.45)], 40), tok([('3', 0.99)], 80)]
    assert read(tokens) == '2*3'


def test_variable_kept_when_it_makes_an_equation():
    tokens = [tok([('2', 0.99)], 0), tok([('x', 0.55), ('×', 0.45)], 40),
              tok([('=', 0.99)], 80), tok([('6', 0.99)], 120)]
    assert read(tokens) == '2*x=6'


def test_digit_preferred_in_exponent():
    # a raised 'z' after a variable is far more likely a misread '2'
    tokens = [tok([('y', 0.99)], 0), tok([('z', 0.6), ('2', 0.4)], 34, y=80, w=16, h=24),
              tok([('=', 0.99)], 70), tok([('9', 0.99)], 110)]
    assert read(tokens) == 'y**(2)=9'


def test_no_parseable_reading_still_returns_one():
    tokens = [tok([('8', 0.99)], 0), tok([('+', 0.6), ('1', 0.4)], 40),
              tok([('=', 0.7), ('+', 0.3)], 80)]
    # '8+=' cannot parse; '81=' cannot either; '8++' no; best parseable is
    # not available, so the decoder still returns some reading
    assert len(choose(tokens)) == 3


def test_single_bar_is_always_minus():
    tokens = [tok([('6', 0.99)], 0), tok([('=', 0.8), ('-', 0.2)], 40, y=117, h=6, shape='bar'),
              tok([('2', 0.99)], 80)]
    assert read(tokens) == '6-2'


def test_merged_bars_are_always_equals():
    tokens = [tok([('x', 0.99)], 0), tok([('-', 0.9), ('=', 0.1)], 40, y=110, h=20, shape='equals'),
              tok([('2', 0.99)], 80)]
    assert read(tokens) == 'x=2'


def test_alternatives_are_kept_for_the_ui():
    tokens = [tok([('2', 0.99)], 0), tok([('x', 0.55), ('×', 0.45)], 40), tok([('3', 0.99)], 80)]
    chosen = choose(tokens)
    assert chosen[1]['char'] == '×'
    assert [c for c, _ in chosen[1]['alternatives']] == ['x', '×']
