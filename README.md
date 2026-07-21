# EQsolver

Handwritten equation solver. Draw an equation on a canvas or upload an image, and the app recognizes the characters with a CNN and solves the equation.

## How it works

1. The React frontend captures a drawn or uploaded equation image.
2. The Flask backend segments the image into individual characters using OpenCV, entirely in memory.
3. A CNN classifies each 28x28 character into a math symbol (`0-9`, `+ - × ÷ =`, `( )`, `√`, and variables `x y z`).
4. A spatial parser reads the 2D layout (superscripts as powers, bars as fractions, radicals as roots) into an explicit expression.
5. SymPy evaluates arithmetic and solves algebraic equations (for example `x²=4` gives `x = -2, 2`), and the result is rendered with KaTeX.

The recognized equation is editable, so a misread is a quick fix rather than a wrong answer. Retraining the classifier on math symbols (see `backend/training/`) is what removed the old letter-substitution guesswork.

## Project structure

- `frontend/` React 18 + Vite app (drawing canvas, upload, results)
- `backend/` Flask API, image segmentation, trained model (`model.h5`)

## The model

A small convolutional classifier that reads one handwritten symbol at a time.

- Served as `backend/model.onnx` (about 1.7 MB, roughly 432k parameters) and run with `onnxruntime`, loaded once at startup. This keeps the app runtime lightweight (no TensorFlow), so it fits small free hosting tiers.
- Trained with TensorFlow/Keras, which produces `backend/model.h5`; `training/convert_to_onnx.py` converts that to the served ONNX file and verifies the predictions match.
- Input: a 28x28 grayscale glyph. Output: 21 classes.
- Classes: digits `0-9`, `+ - × ÷ =`, `( )`, `√`, and variables `x y z`.

Architecture: Conv(32), Conv(32), MaxPool, Dropout, Conv(64), MaxPool, Dropout, Flatten, Dense(128), Dropout, Dense(21, softmax). It classifies each character in isolation; the 2D structure (powers, fractions, roots) is added afterward by the spatial parser, not the network.

### Training

The model is trained on the Kaggle "handwritten math symbols" dataset (xainano). Of its 82 symbol folders, the 21 math-relevant classes are used, each capped at 6,000 images (about 110k total) with balanced class weights and a 90/10 train and validation split. Training runs on CPU in a few minutes (Adam, 20 epochs) and reaches about 98% validation accuracy. See `backend/training/` to reproduce.

Training and inference share the same aspect-preserving preprocessing in `backend/preprocess.py`: threshold to find the ink, crop to it, scale into a 28x28 box keeping the aspect ratio, center, and normalize.

### Limitations

- It reads symbols one at a time with no context, so operators can be misread on handwriting far from the training style. The recognized equation is editable, so any misread is a quick fix before solving.
- The variable `x` and the multiplication sign `×` look nearly identical by hand, which is the model's weakest distinction (about 86%).
- Scope is basic algebra: digits, the four operators, parentheses, powers, fractions, and roots over `x y z`. There is no decimal point, no slash for division (draw `÷` or a fraction bar), and no trigonometry, logarithms, functions, or calculus. Reaching those needs a different, context-aware model (image to LaTeX).

## Setup

### With Docker

Local development (frontend and backend as separate services with hot reload):

```
docker compose up --build
```

Frontend at http://localhost:3000, API at http://localhost:5000.

Production (single image: Flask serves the built frontend and the API on one
port, which is all a container host needs):

```
docker build -t eqsolver .
docker run -p 5000:5000 eqsolver     # open http://localhost:5000
```

### Deploy to Render (free)

The repo has a `render.yaml` blueprint. On https://dashboard.render.com choose
New + Blueprint, connect this repo, and Render builds the root Dockerfile and
serves the app on its free tier. The image ships an ONNX model and no
TensorFlow, so it stays within the free tier's memory.

### Manual

Backend (the app runtime needs only onnxruntime, so any recent Python 3 works;
retraining the model needs Python 3.12 and the `training/requirements.txt` deps):

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

Frontend:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Set `VITE_API_URL` if the API is not on localhost:5000.

## Tests

```
cd backend && pytest
cd frontend && npm test
```

Both suites also run in CI on every push.

## Usage

Draw an equation and click Evaluate, or pick one of the example chips. The segmentation preview, the editable recognized equation, and the solution appear in the results panel beside the canvas. If a symbol is misread, fix it in the recognized field and press Solve.

## API

`POST /predict` with `{"image": "<url-safe base64>"}` returns the recognized characters (each with its confidence and a preview image), the recognized expression, its LaTeX, and the solution:

```json
{
  "characters": [{"char": "8", "confidence": 1.0, "image": "data:image/png;base64,..."}],
  "recognized": "8+3",
  "formatted_equation": "8+3",
  "latex": "8 + 3",
  "solution": "11",
  "solved": true
}
```

`POST /solve` with `{"expression": "x**2=4"}` re-solves an edited expression without the model.

Errors come back as `{"error": "..."}` with a 400 or 422 status.
