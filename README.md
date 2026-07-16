# EQsolver

Handwritten equation solver. Draw an equation on a canvas or upload an image, and the app recognizes the characters with a CNN and solves the equation.

## How it works

1. The React frontend captures a drawn or uploaded equation image.
2. The Flask backend segments the image into individual characters using OpenCV, entirely in memory.
3. A CNN classifies each 28x28 character.
4. SymPy evaluates arithmetic expressions and solves algebraic equations (for example `x2=4` gives `[-2, 2]`).

## Project structure

- `frontend/` React 18 + Vite app (drawing canvas, upload, results)
- `backend/` Flask API, image segmentation, trained model (`model.h5`)

## Setup

### With Docker

```
docker compose up --build
```

Frontend at http://localhost:3000, API at http://localhost:5000.

### Manual

Backend (requires Python 3.12, TensorFlow does not support newer versions yet):

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

Draw an equation and click Evaluate. The recognized equation, its formatted version, and the solution appear below the canvas.

## API

`POST /predict` with `{"image": "<url-safe base64>"}` returns:

```json
{"entered_equation": "8t3", "formatted_equation": "8+3", "solution": "11"}
```

Errors come back as `{"error": "..."}` with a 400 or 422 status.
