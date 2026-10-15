"""Segmentation tests for the '=' merge vs fraction split behaviour, run on
synthetic binary line images (foreground = 255) to avoid the line detector."""
import cv2
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


def test_shape_hints():
    minus = _blank(60, 100)
    minus[30:36, 20:70] = 255
    assert _line_letters(minus)[0]['shape'] == 'bar'
    equals = _blank(60, 100)
    equals[15:21, 20:70] = 255
    equals[35:41, 20:70] = 255
    assert _line_letters(equals)[0]['shape'] == 'equals'


def test_two_stroke_glyph_merges():
    # a 'y' written as two strokes that do not quite touch: '\' then '/'
    img = _blank(100, 100)
    cv2.line(img, (30, 10), (48, 48), 255, 5)
    cv2.line(img, (62, 10), (40, 90), 255, 5)
    img[44:56, 40:56] = 0    # open a gap where they would meet
    pieces = _line_letters(img)
    assert len(pieces) == 1


def test_crossbar_inside_glyph_merges():
    # a 'z' with a separate crossbar: the bar lies inside the glyph's box
    img = _blank(100, 100)
    img[10:16, 20:80] = 255    # top
    img[84:90, 20:80] = 255    # bottom
    img[10:90, 74:80] = 255    # one side joining them (keeps it one contour)
    img[47:53, 35:65] = 255    # crossbar, separate
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] is None


def test_division_sign_merges():
    img = _blank(100, 100)
    img[20:30, 45:55] = 255   # dot above
    img[47:53, 20:80] = 255   # bar
    img[70:80, 45:55] = 255   # dot below
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] is None  # the classifier names it


def test_slanted_equals_strokes_merge():
    img = _blank(80, 120)
    img[20:26, 20:90] = 255   # long upper stroke
    img[44:50, 30:62] = 255   # much shorter lower stroke
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] == 'equals'


def test_radicand_is_not_merged_into_root():
    img = _blank(120, 200)
    img[60:100, 10:16] = 255     # root sign's tick
    img[10:16, 10:190] = 255     # its overbar (same contour via the tick)
    img[10:100, 10:16] = 255
    img[30:100, 60:70] = 255     # radicand digit under the bar
    pieces = _line_letters(img)
    assert len(pieces) == 2


def test_side_by_side_digits_stay_apart():
    img = _blank(80, 140)
    img[10:70, 20:28] = 255
    img[10:70, 60:68] = 255
    img[10:70, 100:108] = 255
    assert len(_line_letters(img)) == 3
