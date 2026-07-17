import warnings
warnings.filterwarnings("ignore")

import base64
import csv
import io
import os

import cv2
import numpy as np
from PIL import Image, ImageOps
# model.h5 is a legacy Keras 2 save; tf_keras is the Keras 2 compat package
from tf_keras.models import load_model

from segmentor import segment_characters

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ROOT, 'model.h5')
MAPPER_PATH = os.path.join(ROOT, 'mapper.csv')

# load the trained model and the id -> character mapping once at import time
model = load_model(MODEL_PATH)
with open(MAPPER_PATH, newline='') as f:
    CODE2CHAR = {int(row['id']): row['char'] for row in csv.DictReader(f)}

ERODE_KERNEL = np.ones((2, 2), np.uint8)


def _to_model_input(crop):
    """Convert one character crop to the 28x28 binary format the CNN expects."""
    eroded = cv2.erode(crop, ERODE_KERNEL, iterations=1)
    img = Image.fromarray(eroded).resize((28, 28))
    inverted = ImageOps.invert(img)
    normalized = np.array(inverted, dtype=float) / 255
    return np.where(normalized > 0.5, 1.0, 0.0)


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

    Returns a list of per-character dicts: {raw, confidence, image}, ordered
    left to right. Everything runs in memory; nothing is written to disk.
    """
    img = _flatten_transparency(Image.open(image_source))
    gray = np.array(img.convert('L'))

    crops = segment_characters(gray)
    if not crops:
        return []

    batch = np.stack([_to_model_input(c) for c in crops]).reshape(-1, 28, 28, 1)
    probs = model.predict(batch, verbose=0)
    classes = np.argmax(probs, axis=1)
    confidences = probs[np.arange(len(probs)), classes]

    characters = []
    for crop, cls, conf in zip(crops, classes, confidences):
        characters.append({
            'raw': CODE2CHAR[int(cls)],
            'confidence': round(float(conf), 4),
            'image': _encode_crop(crop),
        })
    return characters
