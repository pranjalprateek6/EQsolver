import base64
import csv
import io
import os

import numpy as np
import onnxruntime as ort
from PIL import Image

from preprocess import TARGET, to_model_input
from segmentor import segment_characters

ROOT = os.path.dirname(os.path.abspath(__file__))
# the model is served as ONNX so the runtime needs only onnxruntime, not the
# full TensorFlow stack (see training/convert_to_onnx.py); training still uses
# Keras and produces model.h5, which is converted to this model.onnx
MODEL_PATH = os.path.join(ROOT, 'model.onnx')
MAPPER_PATH = os.path.join(ROOT, 'mapper.csv')

# accepted upload formats; anything else is refused before Pillow parses it
IMAGE_FORMATS = ['PNG', 'JPEG', 'WEBP']
# refuse images larger than this before decoding them (about a 6000x4000 photo)
MAX_IMAGE_PIXELS = int(os.environ.get('MAX_IMAGE_PIXELS', str(25_000_000)))
# smallest side in pixels, and the most extreme width:height ratios accepted
# (equations are wide; very tall or ribbon-thin images are not equations)
MIN_IMAGE_SIDE = 16
MAX_WIDE_RATIO = 25
MAX_TALL_RATIO = 4
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class ImageTooLarge(ValueError):
    """The image has more pixels than MAX_IMAGE_PIXELS."""

# load the model and the id -> character mapping once at import time
_session = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
_input_name = _session.get_inputs()[0].name
with open(MAPPER_PATH, newline='', encoding='utf-8') as f:
    CODE2CHAR = {int(row['id']): row['char'] for row in csv.DictReader(f)}


def _encode_crop(crop):
    """Encode a character crop as a small base64 PNG data URL for previewing."""
    buf = io.BytesIO()
    Image.fromarray(crop.astype('uint8')).save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _flatten_transparency(img):
    """Composite transparent images onto white; a transparent canvas export
    turns solid black in grayscale otherwise."""
    if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)
    return img


def open_image(image_source):
    """Open an upload, checking its format and dimensions from the header
    alone so an oversized or odd-shaped image is refused before decoding."""
    try:
        img = Image.open(image_source, formats=IMAGE_FORMATS)
    except Image.DecompressionBombError as exc:
        raise ImageTooLarge('the image is too large') from exc
    width, height = img.size
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageTooLarge('the image is too large')
    if min(width, height) < MIN_IMAGE_SIDE:
        raise ValueError('the image is too small')
    if width > MAX_WIDE_RATIO * height or height > MAX_TALL_RATIO * width:
        raise ValueError('the image is too narrow or too tall to be an equation')
    return img


def recognize(image_source):
    """Recognize the characters in an image (path or file-like object).

    Returns a list of per-character token dicts with the predicted symbol, its
    confidence, a preview image, and the bounding box (x, y, w, h) so the
    spatial parser can read the 2D layout. Ordered left to right; everything
    runs in memory. Raises ImageTooLarge or ValueError for a rejected image
    and OSError for data that is not a supported image.
    """
    img = _flatten_transparency(open_image(image_source))
    gray = np.array(img.convert('L'))

    pieces = segment_characters(gray)
    if not pieces:
        return []

    batch = np.stack([to_model_input(p['crop']) for p in pieces]).reshape(-1, TARGET, TARGET, 1)
    probs = _session.run(None, {_input_name: batch.astype(np.float32)})[0]
    classes = np.argmax(probs, axis=1)
    confidences = probs[np.arange(len(probs)), classes]

    tokens = []
    for piece, cls, conf in zip(pieces, classes, confidences):
        tokens.append({
            'char': CODE2CHAR[int(cls)],
            'confidence': round(float(conf), 4),
            'image': _encode_crop(piece['crop']),
            'x': int(piece['x']), 'y': int(piece['y']),
            'w': int(piece['w']), 'h': int(piece['h']),
        })
    return tokens


def healthcheck():
    """Run the model once on a blank input; raises if inference is broken."""
    blank = np.zeros((1, TARGET, TARGET, 1), dtype=np.float32)
    _session.run(None, {_input_name: blank})
