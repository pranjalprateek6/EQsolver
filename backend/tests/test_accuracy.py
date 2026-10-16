"""Accuracy gate: the whole pipeline must keep reading a fixed set of
handwritten equations about as well as it does today.

fixtures/equations/ holds 60 equation images rendered from real handwritten
glyphs by training/eval_equations.py (seed 7, the first 60 of its benchmark)
and truths.json, what each one says. The training dataset is not needed, so
this runs in CI and fails when a change to segmentation, the model, the
decoder or the spatial parser makes recognition worse.

Regenerate (only when the benchmark itself changes), from backend/:
    python training/eval_equations.py --n 60 --save-dir tests/fixtures/equations
then set BASELINE to the ExpRate it prints.
"""

import io
import json
from pathlib import Path

import pytest

import main as pipeline
from calculator import normalize
from safe_parse import ParseError, parse_tree
from structure import build_expression

FIXTURES = Path(__file__).parent / 'fixtures' / 'equations'

# ExpRate of the shipped model on this set (47 of 60)
BASELINE = 47 / 60
# a few points of slack for float differences between machines; three more
# misreads than today still pass, four fail
THRESHOLD = 0.73


def _read(png):
    try:
        tokens = pipeline.recognize(io.BytesIO(png))
    except ValueError:
        return ''
    return build_expression(tokens) if tokens else ''


def _same(read, truth):
    try:
        return parse_tree(normalize(read)) == parse_tree(normalize(truth))
    except ParseError:
        return False


@pytest.fixture(scope='module')
def results():
    truths = json.loads((FIXTURES / 'truths.json').read_text(encoding='utf-8'))
    out = []
    for name, truth in sorted(truths.items()):
        read = _read((FIXTURES / name).read_bytes())
        out.append((name, truth, read, _same(read, truth)))
    return out


def test_fixture_set_is_complete(results):
    assert len(results) == 60


def test_exprate_has_not_regressed(results):
    exact = sum(ok for *_, ok in results)
    rate = exact / len(results)
    misses = '\n'.join(
        f'  {name}: want {truth!r}, read {read!r}' for name, truth, read, ok in results if not ok
    )
    print(f'\nExpRate {rate:.1%} ({exact}/{len(results)}), baseline {BASELINE:.1%}\n{misses}')
    assert rate >= THRESHOLD, (
        f'ExpRate fell to {rate:.1%} ({exact}/{len(results)}); the gate is {THRESHOLD:.0%} '
        f'(baseline {BASELINE:.1%}). Misread:\n{misses}'
    )
