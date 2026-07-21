"""Convert the trained Keras model (model.h5) to ONNX (model.onnx) so the app
can run inference with the lightweight onnxruntime instead of TensorFlow.

Run after training:
    python training/convert_to_onnx.py
"""
import os
import sys

import numpy as np
import tensorflow as tf
import tf2onnx
from tf_keras.models import load_model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H5_PATH = os.path.join(ROOT, 'model.h5')
ONNX_PATH = os.path.join(ROOT, 'model.onnx')


def main():
    model = load_model(H5_PATH)
    spec = (tf.TensorSpec((None, 28, 28, 1), tf.float32, name='input'),)
    tf2onnx.convert.from_keras(model, input_signature=spec, opset=15, output_path=ONNX_PATH)

    # verify the ONNX model gives the same predictions as the Keras model
    import onnxruntime as ort
    rng = np.random.RandomState(0)
    sample = rng.rand(32, 28, 28, 1).astype(np.float32)
    keras_pred = np.argmax(model.predict(sample, verbose=0), axis=1)
    session = ort.InferenceSession(ONNX_PATH)
    name = session.get_inputs()[0].name
    onnx_pred = np.argmax(session.run(None, {name: sample})[0], axis=1)

    agree = int((keras_pred == onnx_pred).sum())
    print(f'saved {ONNX_PATH}')
    print(f'prediction agreement: {agree}/{len(sample)}')
    if agree != len(sample):
        sys.exit('ONNX predictions diverge from Keras, aborting')


if __name__ == '__main__':
    main()
