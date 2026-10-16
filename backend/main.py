import base64
import csv
import io
import os

import numpy as np
import onnxruntime as ort
from PIL import Image

import decode
from preprocess import TARGET, to_model_input
from segmentor import segment_characters, segment_lines

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


# how many of the model's best guesses to keep per glyph; the context decoder
# chooses among them, and the UI offers them as one-tap corrections
TOP_K = 3
# 'context' picks the reading that makes the most sense as a whole equation;
# 'greedy' takes each glyph's single best guess (the old behaviour)
DEFAULT_DECODER = os.environ.get('EQSOLVER_DECODER', 'context')


def recognize(image_source, decoder=None):
    """Recognize the characters in an image (path or file-like object).

    Returns a list of per-character token dicts with the chosen symbol, its
    confidence, the model's top alternatives, a preview image, and the
    bounding box (x, y, w, h) so the spatial parser can read the 2D layout.
    Ordered left to right; everything runs in memory. Raises ImageTooLarge or
    ValueError for a rejected image and OSError for data that is not a
    supported image.
    """
    return _classify(segment_characters(_gray(image_source)), decoder)


def recognize_lines(image_source, decoder=None):
    """Recognize several lines of working, one equation per line.

    Returns one token list (as from recognize) per written line, top line
    first. Raises like recognize.
    """
    return [tokens for tokens in (_classify(pieces, decoder)
                                  for pieces in segment_lines(_gray(image_source))) if tokens]


def _gray(image_source):
    img = _flatten_transparency(open_image(image_source))
    return np.array(img.convert('L'))


def _classify(pieces, decoder=None):
    if not pieces:
        return []

    batch = np.stack([to_model_input(p['crop']) for p in pieces]).reshape(-1, TARGET, TARGET, 1)
    probs = _session.run(None, {_input_name: batch.astype(np.float32)})[0]
    ranked = np.argsort(-probs, axis=1)[:, :TOP_K]

    tokens = []
    for piece, row, order in zip(pieces, probs, ranked):
        alternatives = [(CODE2CHAR[int(c)], round(float(row[c]), 4)) for c in order]
        tokens.append({
            'char': alternatives[0][0],
            'confidence': alternatives[0][1],
            'alternatives': alternatives,
            'image': _encode_crop(piece['crop']),
            'x': int(piece['x']), 'y': int(piece['y']),
            'w': int(piece['w']), 'h': int(piece['h']),
            'shape': piece.get('shape'),
        })

    if (decoder or DEFAULT_DECODER) == 'context':
        tokens = decode.choose(tokens)
    return tokens


def healthcheck():
    """Run the model once on a blank input; raises if inference is broken."""
    blank = np.zeros((1, TARGET, TARGET, 1), dtype=np.float32)
    _session.run(None, {_input_name: blank})
