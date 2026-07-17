"""Shared image preprocessing for both training and inference.

Every character, whether a training sample or a crop segmented from a drawn
equation, is normalized the same way: binarize, crop to the ink, scale to fit
a 28x28 box while preserving aspect ratio, and centre it. Preserving aspect
ratio is the key fix over the old naive resize, which squashed tall glyphs
like '1' and wide ones like '-' into squares unlike the training data.
"""
import cv2
import numpy as np

TARGET = 28
# blank margin kept around the glyph inside the 28x28 box
PAD = 4


def to_model_input(gray):
    """Normalize a grayscale crop (dark ink on light background) to a 28x28
    float array with ink near 1.0 and background 0.0.

    The image is kept as antialiased grayscale rather than re-binarized after
    downscaling: shrinking a thin binary stroke averages it down to faint
    values, so a hard threshold afterwards erases thin glyphs like '1' or '+'.
    """
    # Otsu mask, only used to find the ink bounding box
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return np.zeros((TARGET, TARGET), dtype=np.float32)

    # invert so ink is bright, then crop to the glyph
    inverted = 255.0 - gray.astype(np.float32)
    crop = inverted[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape

    inner = TARGET - 2 * PAD
    scale = inner / max(h, w)
    nh = max(1, int(round(h * scale)))
    nw = max(1, int(round(w * scale)))
    resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((TARGET, TARGET), dtype=np.float32)
    oy = (TARGET - nh) // 2
    ox = (TARGET - nw) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized

    # scale to 0..1 by the glyph's own peak so faint strokes keep full contrast
    peak = canvas.max()
    if peak > 0:
        canvas /= peak
    return canvas
