import warnings
warnings.filterwarnings("ignore")

import base64
import csv
import io
import os

import numpy as np
from PIL import Image
# model.h5 is a legacy Keras 2 save; tf_keras is the Keras 2 compat package
from tf_keras.models import load_model

from preprocess import TARGET, to_model_input
from segmentor import segment_characters

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ROOT, 'model.h5')
MAPPER_PATH = os.path.join(ROOT, 'mapper.csv')

# load the trained model and the id -> character mapping once at import time
model = load_model(MODEL_PATH)
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
    probs = model.predict(batch, verbose=0)
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
