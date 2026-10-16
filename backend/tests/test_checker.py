"""Checking a student's working line by line (checker.check_lines)."""
import pytest

from checker import DIFFERENT, MAX_LINES, MIXED, NOT_EQUAL, UNCHECKED, UNREADABLE, check_lines


def oks(lines):
    return [row['ok'] for row in check_lines(lines)['lines']]


def reason(lines, index=1):
    return check_lines(lines)['lines'][index]['reason']


@pytest.mark.parametrize('lines', [
    ['2x+3=11', '2x=8', 'x=4'],
    ['2x+3=11', '2x=11-3', 'x=8/2', 'x=4'],
    ['3(x-2)=x+4', '3x-6=x+4', '2x=10', 'x=5'],
    ['x/2+1=4', 'x/2=3', 'x=6'],
    ['x^2-5x+6=0', '(x-2)(x-3)=0'],
    ['x^2=4', 'x^2-4=0'],
    ['4=2x', 'x=2'],                  # sides swapped
    ['x^3=8', 'x=2'],                 # real solutions, as students solve
    ['2x+3y=6', '3y=6-2x', 'y=(6-2x)/3'],  # several variables
    ['3+5=8', '8=8'],                 # plain arithmetic, both true
])
def test_correct_chains(lines):
    result = check_lines(lines)
    assert all(row['ok'] is True for row in result['lines'])
    assert result['first_error'] is None


def test_first_line_is_the_problem():
    rows = check_lines(['2x+3=11'])['lines']
    assert rows[0]['ok'] is True and rows[0]['reason'] == ''


def test_rows_carry_text_and_latex():
    row = check_lines(['2x+3=11', 'x^2=8'])['lines'][1]
    assert row['text'] == 'x^2=8'
    assert row['latex'] == 'x^{2} = 8'


def test_finished_only_for_a_correct_x_equals_number():
    assert check_lines(['2x+3=11', '2x=8', 'x=4'])['finished'] is True
    assert check_lines(['2x+3=11', '2x=8'])['finished'] is False
    assert check_lines(['2x+3=11', 'x=5'])['finished'] is False
    assert check_lines(['x=4'])['finished'] is False  # nothing was worked


@pytest.mark.parametrize('lines, term, fixed', [
    (['2x+3=11', '2x=11+3'], '3', '-3'),
    (['2x+3=11', '2x=14', 'x=7'], '3', '-3'),       # moved and added up
    (['3x-6=9', '3x=3'], '-6', '6'),
    (['5x=2x+9', '7x=9'], '2x', '-2x'),            # a variable term
    (['x+4=10', 'x=(10+4)'], '4', '-4'),
])
def test_sign_error_when_moving_a_term(lines, term, fixed):
    text = reason(lines)
    assert check_lines(lines)['lines'][1]['ok'] is False
    assert f'moved {term} across' in text and f'become {fixed}' in text


@pytest.mark.parametrize('lines, words', [
    (['2x=8', 'x=8'], 'divided only the left side by 2'),
    (['8=2x', '8=x'], 'divided only the right side by 2'),
    (['3x+3=12', 'x+1=12'], 'divided only the left side by 3'),
    (['x/2=3', 'x=3'], 'multiplied only the left side by 2'),
    (['-x=4', 'x=4'], 'changed the sign of the left side only'),
])
def test_one_side_only(lines, words):
    assert words in reason(lines)


@pytest.mark.parametrize('lines', [
    ['x^2=4', 'x=2'],
    ['x^2=2x', 'x=2'],                         # divided by x
    ['(x-2)(x-3)=0', 'x=2'],
])
def test_lost_root(lines):
    assert oks(lines)[1] is False
    assert 'lost a solution' in reason(lines)


@pytest.mark.parametrize('lines', [
    ['sqrt(x)=x-2', 'x=(x-2)^2'],              # squared both sides
    ['x=2', 'x^2=2x'],                         # multiplied by x
])
def test_extraneous_root(lines):
    assert oks(lines)[1] is False
    assert 'gained a solution' in reason(lines)


def test_hints_never_contain_the_answer():
    for lines in (['2x+3=11', '2x=11+3'], ['x^2=4', 'x=2'], ['2x+3=11', 'x=5'],
                  ['sqrt(x)=x-2', 'x=(x-2)^2'], ['2x=8', 'x=8']):
        rows = check_lines(lines)['lines']
        assert 'answer_latex' not in check_lines(lines)
        # the solution 4 / 2 / 4 of the first line is never named
        assert not any(f'x = {v}' in r['reason'] or f'x={v}' in r['reason']
                       for r in rows for v in ('4', '-2', '2'))


def test_generic_reason_otherwise():
    assert reason(['2x+3=11', 'x=5']) == DIFFERENT


@pytest.mark.parametrize('lines, expected', [
    (['2(x+1)=2x+2', '2x+2=2x+2', '0=0'], [True, True, True]),  # an identity
    (['2x+3=11', '0=0'], [True, False]),        # an equation is not an identity
    (['x+1=x+2', '1=2'], [True, True]),          # no solution either way
    (['x+1=x+2', '0=0'], [True, False]),
])
def test_identity_lines(lines, expected):
    assert oks(lines) == expected


def test_only_first_error_is_reported_as_first():
    result = check_lines(['2x+3=11', '2x=14', 'x=7', 'x=8'])
    assert [r['ok'] for r in result['lines']] == [True, False, True, False]
    assert result['first_error'] == 1


def test_unreadable_line():
    result = check_lines(['2x+3=11', '2x+=', 'x=4'])
    assert result['lines'][1] == {'text': '2x+=', 'latex': '', 'ok': False, 'reason': UNREADABLE}
    # the next line is compared with the last readable one
    assert result['lines'][2]['ok'] is True


def test_hostile_text_is_unreadable_not_run():
    row = check_lines(['x=1', "__import__('os').system('id')"])['lines'][1]
    assert row['ok'] is False and row['reason'] == UNREADABLE


def test_mixed_equations_and_expressions():
    assert reason(['x+1=3', 'x+2']) == MIXED


def test_expression_simplification():
    assert oks(['(x+1)^2', 'x^2+2x+1']) == [True, True]
    assert reason(['(x+1)^2', 'x^2+1']) == NOT_EQUAL


def test_several_variables_that_cannot_be_compared():
    # not a rearrangement and not decidable from one variable: say so
    assert check_lines(['x+y=3', 'x=1'])['lines'][1] == {
        'text': 'x=1', 'latex': 'x = 1', 'ok': None, 'reason': UNCHECKED}


def test_line_limit():
    result = check_lines(['x=1'] * (MAX_LINES + 5))
    assert len(result['lines']) == MAX_LINES


def test_reveal():
    assert check_lines(['2x+3=11', '2x=8'], reveal=True)['answer_latex'] == 'x = 4'
    assert check_lines(['x^2=4'], reveal=True)['answer_latex'] == 'x = -2, 2'
    assert check_lines(['2x+'], reveal=True)['answer_latex'] == ''
