"""Segmentation tests for the '=' merge vs fraction split behaviour, run on
synthetic binary line images (foreground = 255) to avoid the line detector."""
import numpy as np

from segmentor import _line_letters, _is_bar


def _blank(h, w):
    return np.zeros((h, w), dtype=np.uint8)


def test_is_bar():
    assert _is_bar(50, 6)       # wide, short -> bar
    assert not _is_bar(20, 40)  # tall glyph -> not a bar


def test_equals_merges_to_one_box():
    img = _blank(60, 100)
    img[15:21, 20:70] = 255  # upper stroke
    img[35:41, 20:70] = 255  # lower stroke
    pieces = _line_letters(img)
    assert len(pieces) == 1
    box = pieces[0]
    # the single box spans both strokes vertically
    assert box['h'] >= 20


def test_fraction_stays_three_boxes():
    img = _blank(120, 100)
    img[5:45, 45:52] = 255    # numerator '1' (tall)
    img[55:61, 25:75] = 255   # fraction bar (wide, short)
    img[70:110, 40:60] = 255  # denominator (tall)
    pieces = _line_letters(img)
    assert len(pieces) == 3
    # exactly one of them is the wide bar
    bars = [p for p in pieces if _is_bar(p['w'], p['h'])]
    assert len(bars) == 1
    bar = bars[0]
    above = [p for p in pieces if p['y'] + p['h'] <= bar['y']]
    below = [p for p in pieces if p['y'] >= bar['y'] + bar['h']]
    assert len(above) == 1 and len(below) == 1


def test_standalone_minus_stays_one_box():
    img = _blank(60, 100)
    img[30:36, 20:70] = 255
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert _is_bar(pieces[0]['w'], pieces[0]['h'])
