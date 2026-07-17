"""Preprocessing tests: aspect ratio is preserved and glyphs are centred."""
import numpy as np

from preprocess import TARGET, to_model_input


def _canvas(h=120, w=120):
    # white background (255), we draw dark ink (0) onto it
    return np.full((h, w), 255, dtype=np.uint8)


def test_output_shape_and_range():
    img = _canvas()
    img[40:80, 40:80] = 0  # a solid square blob
    out = to_model_input(img)
    assert out.shape == (TARGET, TARGET)
    assert out.min() >= 0.0 and out.max() <= 1.0
    assert out.max() > 0.9  # ink survives at full contrast


def test_thin_stroke_survives():
    # a thin stroke must not be erased by downscaling (the original bug)
    img = _canvas()
    img[20:100, 58:62] = 0
    out = to_model_input(img)
    assert out.sum() > 5


def test_blank_image_is_empty():
    out = to_model_input(_canvas())
    assert out.sum() == 0


def test_tall_stroke_stays_tall():
    # a thin vertical line (like a '1') must not be stretched into a square
    img = _canvas()
    img[20:100, 58:64] = 0
    out = to_model_input(img)
    ink_rows = np.where(out.sum(axis=1) > 0)[0]
    ink_cols = np.where(out.sum(axis=0) > 0)[0]
    height = ink_rows.max() - ink_rows.min() + 1
    width = ink_cols.max() - ink_cols.min() + 1
    assert height > 3 * width  # clearly taller than wide, aspect preserved


def test_glyph_is_centred():
    # ink placed off-centre should be re-centred in the 28x28 box
    img = _canvas()
    img[10:40, 10:40] = 0
    out = to_model_input(img)
    ink_rows = np.where(out.sum(axis=1) > 0)[0]
    ink_cols = np.where(out.sum(axis=0) > 0)[0]
    row_mid = (ink_rows.min() + ink_rows.max()) / 2
    col_mid = (ink_cols.min() + ink_cols.max()) / 2
    assert abs(row_mid - TARGET / 2) <= 2
    assert abs(col_mid - TARGET / 2) <= 2
