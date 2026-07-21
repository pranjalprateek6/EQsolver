import warnings
warnings.filterwarnings("ignore")

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


def recognize(image_source):
    """Recognize the characters in an image (path or file-like object).

    Returns a list of per-character token dicts with the predicted symbol, its
    confidence, a preview image, and the bounding box (x, y, w, h) so the
    spatial parser can read the 2D layout. Ordered left to right; everything
    runs in memory.
    """
    img = _flatten_transparency(Image.open(image_source))
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
