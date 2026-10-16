"""Segmentation tests for the '=' merge vs fraction split behaviour, run on
synthetic binary line images (foreground = 255) to avoid the line detector."""

import cv2
import numpy as np

from segmentor import _is_bar, _line_letters


def _blank(h, w):
    return np.zeros((h, w), dtype=np.uint8)


def test_is_bar():
    assert _is_bar(50, 6)  # wide, short -> bar
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
    img[5:45, 45:52] = 255  # numerator '1' (tall)
    img[55:61, 25:75] = 255  # fraction bar (wide, short)
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
    img[44:56, 40:56] = 0  # open a gap where they would meet
    pieces = _line_letters(img)
    assert len(pieces) == 1


def test_crossbar_inside_glyph_merges():
    # a 'z' with a separate crossbar: the bar lies inside the glyph's box
    img = _blank(100, 100)
    img[10:16, 20:80] = 255  # top
    img[84:90, 20:80] = 255  # bottom
    img[10:90, 74:80] = 255  # one side joining them (keeps it one contour)
    img[47:53, 35:65] = 255  # crossbar, separate
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] is None


def test_division_sign_merges():
    img = _blank(100, 100)
    img[20:30, 45:55] = 255  # dot above
    img[47:53, 20:80] = 255  # bar
    img[70:80, 45:55] = 255  # dot below
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] is None  # the classifier names it


def test_slanted_equals_strokes_merge():
    img = _blank(80, 120)
    img[20:26, 20:90] = 255  # long upper stroke
    img[44:50, 30:62] = 255  # much shorter lower stroke
    pieces = _line_letters(img)
    assert len(pieces) == 1
    assert pieces[0]['shape'] == 'equals'


def test_radicand_is_not_merged_into_root():
    img = _blank(120, 200)
    img[60:100, 10:16] = 255  # root sign's tick
    img[10:16, 10:190] = 255  # its overbar (same contour via the tick)
    img[10:100, 10:16] = 255
    img[30:100, 60:70] = 255  # radicand digit under the bar
    pieces = _line_letters(img)
    assert len(pieces) == 2


def test_side_by_side_digits_stay_apart():
    img = _blank(80, 140)
    img[10:70, 20:28] = 255
    img[10:70, 60:68] = 255
    img[10:70, 100:108] = 255
    assert len(_line_letters(img)) == 3


# --- splitting several lines of working (the check-my-work flow) ---

from segmentor import segment_lines, split_lines  # noqa: E402


def _glyph(img, x, y, w=24, h=48):
    img[y : y + h, x : x + w] = 255


def test_split_lines_on_large_gaps():
    img = _blank(400, 300)
    for x in (20, 60, 100):
        _glyph(img, x, 20)  # line 1
        _glyph(img, x, 160)  # line 2
        _glyph(img, x, 300)  # line 3
    bands = split_lines(img)
    assert len(bands) == 3
    assert bands[0][0] <= 20 and bands[0][1] >= 68
    assert bands[2][0] <= 300


def test_split_lines_single_line_is_one_band():
    img = _blank(120, 300)
    for x in (20, 60, 100):
        _glyph(img, x, 30)
    assert len(split_lines(img)) == 1
    assert split_lines(_blank(50, 50)) == []


def test_split_lines_keeps_a_loose_fraction_whole():
    # a fraction written loosely on a line of its own: the numerator and
    # denominator are further from the bar than the line gap, but the bar
    # has ink directly above and below, so it is one line
    img = _blank(300, 300)
    _glyph(img, 120, 0, h=40)  # numerator
    img[76:82, 105:160] = 255  # fraction bar, 36px below it
    _glyph(img, 120, 112, h=40)  # denominator, 30px below the bar
    assert split_lines(img) == [(0, 152)]


def test_split_lines_keeps_a_loose_fraction_beside_glyphs():
    # 'x + 1/2' with the denominator dropped well below the bar
    img = _blank(300, 300)
    _glyph(img, 20, 30)  # x, centred on the bar
    _glyph(img, 60, 30)  # +
    _glyph(img, 120, 0, h=40)  # numerator
    img[52:58, 105:160] = 255  # fraction bar
    _glyph(img, 120, 112, h=40)  # denominator, 54px below it
    assert split_lines(img) == [(0, 152)]


def test_split_lines_minus_or_equals_is_not_a_fraction_bar():
    # line 1 ends mid-line with '=' and '-' strokes; the glyphs of line 2
    # sit right under them, but these are not fraction bars
    img = _blank(300, 300)
    _glyph(img, 20, 20)
    img[38:42, 60:100] = 255  # '=' upper
    img[52:56, 60:100] = 255  # '=' lower
    img[45:49, 120:160] = 255  # minus
    _glyph(img, 150, 20)
    for x in (65, 125):
        _glyph(img, x, 110)  # line 2
    assert len(split_lines(img)) == 2


def test_split_lines_detached_top_of_a_seven():
    # a '7' whose top stroke came off is not a fraction bar over the line above
    img = _blank(300, 300)
    for x in (20, 60):
        _glyph(img, x, 20)  # line 1
    img[110:115, 15:75] = 255  # the 7's top stroke
    img[118:166, 50:60] = 255  # the 7's stem
    _glyph(img, 100, 110)
    assert len(split_lines(img)) == 2


def test_split_lines_keeps_an_exponent_whole():
    img = _blank(300, 300)
    _glyph(img, 20, 60)  # x
    _glyph(img, 46, 30, w=14, h=26)  # raised exponent
    _glyph(img, 80, 60)
    assert len(split_lines(img)) == 1


def test_split_lines_fraction_on_second_line():
    img = _blank(500, 300)
    for x in (20, 60, 100):
        _glyph(img, x, 30)  # line 1
    _glyph(img, 120, 200)  # numerator
    img[262:268, 105:160] = 255  # bar
    _glyph(img, 120, 285)  # denominator
    _glyph(img, 20, 245)  # x beside the fraction
    bands = split_lines(img)
    assert len(bands) == 2
    assert bands[1][0] <= 200 and bands[1][1] >= 333


def test_segment_lines_returns_pieces_per_line():
    # white paper with black ink, as an upload or canvas export would be
    gray = np.full((400, 600), 255, dtype=np.uint8)
    for row in (40, 220):
        for x in (40, 140, 240):
            cv2.rectangle(gray, (x, row), (x + 40, row + 90), 0, 6)
    lines = segment_lines(gray)
    assert len(lines) == 2
    assert all(len(pieces) == 3 for pieces in lines)
    assert lines[0][0]['y'] < lines[1][0]['y']
