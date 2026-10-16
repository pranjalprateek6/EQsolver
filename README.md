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

Whole-equation accuracy is measured with `backend/training/eval_equations.py` (about 74% of equations read exactly right), and a committed 60-equation sample keeps it from regressing: `backend/tests/test_accuracy.py` fails CI if ExpRate on it drops below 73%.

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

Both suites also run in CI on every push, along with a job that builds the
production Docker image and smoke-tests it (health check, a solve, a hostile
input, and a runaway solve that must be cut off).

## Usage

Draw an equation and click Evaluate, or pick one of the example chips. The segmentation preview, the editable recognized equation, and the solution appear in the results panel beside the canvas. If a symbol is misread, fix it in the recognized field and press Solve.

**Check my work** (the switch under the title) checks a student's working
instead of solving it. Write the problem on the first ruled line and each step
on the next, one equation per line (or type them). Every line is checked
against the line above it: a correct step keeps the same solutions. The first
line that changes them is highlighted with a short hint (a sign error when
moving a term, multiplying or dividing only one side, a lost or extra
solution), and the answer stays hidden until you press "Show the answer". Tap
"Fix reading" on a handwritten line to correct a misread symbol.

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

Each character also carries `alternatives` (the model's top 3 guesses with
their confidences) and its box `x`, `y`, `w`, `h`. The chosen `char` is picked
by a context decoder that scores whole readings, so it is not always the
single most likely guess (see `backend/training/README.md` for how this is
measured).

`POST /solve` with `{"expression": "x**2=4"}` re-solves an edited expression without the model.

`POST /rebuild` with `{"characters": [{"char": "x", "x": 0, "y": 100, "w": 28, "h": 40}, ...]}`
re-reads characters after the user corrects some of them (tapping a tile in
the UI). Positions are kept, so powers, fractions and roots are still read
from the layout. It returns the same fields as `/predict` minus `characters`.

`POST /check` with `{"lines": ["2x+3=11", "2x=11+3", "x=7"]}` (or a
handwritten page as `{"image": "<url-safe base64>"}`, one equation per line)
checks a student's working, at most 12 lines:

```json
{
  "lines": [
    {"text": "2x+3=11", "latex": "2 x + 3 = 11", "ok": true, "reason": ""},
    {"text": "2x=11+3", "latex": "2 x = 11 + 3", "ok": false,
     "reason": "check the sign when you moved 3 across the =: it should become -3 on the other side"},
    {"text": "x=7", "latex": "x = 7", "ok": true, "reason": ""}
  ],
  "first_error": 1,
  "finished": false
}
```

`ok` is `null` for a step that could not be checked. Each line is compared
with the one before (over the real numbers), so `x=7` above is a correct step
from its own previous line. Handwritten lines also carry `characters`, for
`/rebuild`. The answer is only included, as `answer_latex`, when the request
sets `"reveal": true`.

Expressions use `+ - * / ** ^ =`, parentheses, `sqrt(...)`, `pi`, decimals and
single-letter variables; juxtaposition multiplies (`2x`, `3(x+1)`). Anything
else is refused.

`GET /healthz` runs one model inference and one sandboxed solve, and returns
`{"status": "ok"}` or a 503.

Errors come back as `{"error": "..."}` with a 400 (bad request), 413 (upload
too large), 422 (unreadable or unsolvable) or 429 (rate limited) status.

## Security and limits

- Expressions are parsed by an allowlisted grammar (`backend/safe_parse.py`)
  that builds SymPy objects directly. Nothing user-supplied reaches `eval`, and
  power towers like `9**9**9**9` are refused before they are computed.
- Every solve runs in a pool of separate processes (`backend/sandbox.py`) with
  a time limit, and on Linux a memory cap. A solve that overruns is killed, so
  one hard equation cannot stall the server.
- Uploads are limited by request size, pixel count, shape and format (PNG,
  JPEG, WebP), checked from the image header before decoding.
- Requests to `/predict`, `/solve`, `/rebuild` and `/check` are rate limited per client.

## Configuration

All settings are environment variables with production-safe defaults.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `5000` | Port to bind |
| `WEB_CONCURRENCY` | `1` | gunicorn worker processes |
| `GUNICORN_THREADS` | `4` | Threads per worker |
| `SOLVE_TIMEOUT` | `3` | Seconds a solve may run before it is killed |
| `CHECK_TIMEOUT` | `8` | Seconds a whole `/check` (all its lines) may run |
| `SOLVER_PROCESSES` | `2` | Solver processes per worker |
| `SOLVER_MEMORY_MB` | `256` | Extra memory a solver process may use (Linux) |
| `MAX_REQUEST_BYTES` | `10485760` | Largest request body |
| `MAX_IMAGE_PIXELS` | `25000000` | Largest image, in pixels |
| `RATE_LIMIT` | `30 per minute` | Per-client limit on each API endpoint |
| `RATELIMIT_STORAGE_URI` | `memory://` | Shared limiter storage, for example `redis://...` |
| `PROXY_COUNT` | `0` | Reverse proxies in front of the app (Render: `1`) |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed cross-origin callers |
| `FLASK_DEBUG` | unset | `1` enables the debugger for `python app.py` |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_FORMAT` | `json` | `json` (one object per line) or `text` for a readable local console |
| `SENTRY_DSN` | unset | Backend error tracking; Sentry is off unless this is set |
| `SENTRY_ENVIRONMENT` | `production` (`preview` on Render PR previews) | Environment name on backend Sentry events |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` | Share of requests sent to Sentry as performance traces |
| `VITE_SENTRY_DSN` | unset | Frontend error tracking, read at **build** time (a Docker build arg; on Render, set it as an environment variable before the deploy) |
| `VITE_SENTRY_ENVIRONMENT` | `production` | Environment name on frontend Sentry events (build time) |

### Logs and error tracking

Every request is logged as one JSON line with its method, path, endpoint,
status, latency and a request id; health checks are only logged when they
fail. Send an `X-Request-ID` header to choose the id (letters, digits and
`._:-`, up to 128 characters), otherwise one is generated; either way it comes
back in the `X-Request-ID` response header and is tagged on Sentry events, so a
report from a user can be matched to the log lines. Request bodies, query
strings and images are never logged.

To turn on Sentry, create a project for Flask and one for React at
[sentry.io](https://sentry.io) (the free tier is enough), then set
`SENTRY_DSN` and `VITE_SENTRY_DSN` on the Render service and redeploy. Events
never include request bodies, cookies, user details or stack-frame variables,
and any image data is blanked before it is sent; expressions can appear in
error messages. Without the DSNs nothing is sent and the frontend does not
even download the Sentry code.

Dependencies are pinned in `backend/requirements.txt`, generated from
`backend/requirements.in` with `uv pip compile` (the command is in the file).
