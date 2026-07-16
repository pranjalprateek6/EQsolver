# EQsolver

Handwritten equation solver. Draw an equation on a canvas or upload an image, and the app recognizes the characters with a CNN and solves the equation.

## How it works

1. The React frontend captures a drawn or uploaded equation image.
2. The Flask backend segments the image into individual characters using OpenCV.
3. A CNN classifies each 28x28 character.
4. SymPy evaluates arithmetic expressions and solves algebraic equations (for example `x2=4` gives `[-2, 2]`).

## Project structure

- `src/` React frontend (drawing canvas, upload, results)
- `Equation-Solver/` Flask API, image segmentation, trained model (`model.h5`)

## Setup

### Backend

Requires Python 3.12 (TensorFlow does not support newer versions yet).

```
cd Equation-Solver
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

The API runs on http://localhost:5000.

### Frontend

```
npm install
npm start
```

Open http://localhost:3000/equations-solver.

## Usage

Draw an equation, click Save, then click Evaluate. The recognized equation, its formatted version, and the solution appear below the canvas.
