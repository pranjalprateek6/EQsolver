"""Train the Level 2 handwritten math-symbol classifier.

Trains a small CNN on the Kaggle "Handwritten math symbols" dataset (or any
folder-per-class image set), using the same aspect-preserving preprocessing as
inference. Exports a model.h5 and a mapper.csv that drop straight into the
Flask backend.

Usage:
    python training/train.py --data-dir data/extracted_images --epochs 15
    python training/train.py --smoke        # tiny synthetic run to prove the pipeline
"""
import argparse
import csv
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from preprocess import TARGET, to_model_input  # noqa: E402

# dataset folder name -> the symbol the model should emit. Folders not listed
# here are ignored, so the model spends its capacity only on math symbols.
CLASS_MAP = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
    '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '+': '+', '-': '-', '=': '=',
    'times': '×', 'div': '÷', 'forward_slash': '/',
    '(': '(', ')': ')',
    'x': 'x', 'y': 'y', 'z': 'z',
    'sqrt': '√', 'dot': '.', '.': '.',
}


def load_dataset(data_dir, per_class_limit=None):
    images, labels, symbols = [], [], []
    for folder in sorted(os.listdir(data_dir)):
        symbol = CLASS_MAP.get(folder)
        if symbol is None:
            continue
        folder_path = os.path.join(data_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        if symbol not in symbols:
            symbols.append(symbol)
        label = symbols.index(symbol)
        files = sorted(os.listdir(folder_path))
        if per_class_limit:
            files = files[:per_class_limit]
        for name in files:
            gray = cv2.imread(os.path.join(folder_path, name), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                continue
            images.append(to_model_input(gray))
            labels.append(label)
    x = np.array(images, dtype=np.float32).reshape(-1, TARGET, TARGET, 1)
    y = np.array(labels, dtype=np.int64)
    return x, y, symbols


def build_model(num_classes):
    from tf_keras import layers, models
    model = models.Sequential([
        layers.Input((TARGET, TARGET, 1)),
        layers.Conv2D(32, 3, activation='relu', padding='same'),
        layers.Conv2D(32, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),
        layers.Dropout(0.25),
        layers.Conv2D(64, 3, activation='relu', padding='same'),
        layers.MaxPooling2D(),
        layers.Dropout(0.25),
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5),
        layers.Dense(num_classes, activation='softmax'),
    ])
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy',
                  metrics=['accuracy'])
    return model


def make_synthetic(symbols, per_class=40):
    """Random blobs, only used by --smoke to prove the pipeline runs."""
    rng = np.random.RandomState(0)
    images, labels = [], []
    for label, _ in enumerate(symbols):
        for _ in range(per_class):
            img = np.full((48, 48), 255, np.uint8)
            cx, cy = rng.randint(12, 36, size=2)
            cv2.circle(img, (cx, cy), 6 + label % 6, 0, -1)
            images.append(to_model_input(img))
            labels.append(label)
    x = np.array(images, dtype=np.float32).reshape(-1, TARGET, TARGET, 1)
    y = np.array(labels, dtype=np.int64)
    return x, y


def write_mapper(symbols, path):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'char'])
        for i, symbol in enumerate(symbols):
            writer.writerow([i, symbol])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default='data/extracted_images')
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--per-class-limit', type=int, default=None)
    parser.add_argument('--out-model', default='model_v2.h5')
    parser.add_argument('--out-mapper', default='mapper_v2.csv')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()

    if args.smoke:
        symbols = ['0', '1', '+', 'x']
        x, y = make_synthetic(symbols)
        epochs = 1
    else:
        x, y, symbols = load_dataset(args.data_dir, args.per_class_limit)
        epochs = args.epochs
        print(f'loaded {len(x)} images across {len(symbols)} classes: {symbols}')

    if len(x) == 0:
        raise SystemExit('no images loaded, check --data-dir and CLASS_MAP')

    perm = np.random.RandomState(42).permutation(len(x))
    x, y = x[perm], y[perm]
    split = int(len(x) * 0.9)

    model = build_model(len(symbols))
    model.fit(x[:split], y[:split], validation_data=(x[split:], y[split:]),
              epochs=epochs, batch_size=128, verbose=2)

    model.save(args.out_model)
    write_mapper(symbols, args.out_mapper)
    print(f'saved {args.out_model} and {args.out_mapper}')


if __name__ == '__main__':
    main()
