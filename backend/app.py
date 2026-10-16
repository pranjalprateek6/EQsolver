import base64
import binascii
import logging
import os
from io import BytesIO

from flask import Flask, jsonify, request, send_from_directory
from flask_compress import Compress
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import sandbox
from checker import MAX_LINES
from main import CODE2CHAR, ImageTooLarge, healthcheck, recognize, recognize_lines
from observability import configure_logging, init_request_logging, init_sentry
from safe_parse import MAX_LENGTH
from structure import build_expression

configure_logging()
log = logging.getLogger('eqsolver')
# before the app is created, so the Flask integration hooks in
init_sentry()

# in a production build the compiled frontend is copied here and served by Flask
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
# a base64 phone photo is about 4/3 of the file size; refuse anything bigger
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_REQUEST_BYTES', str(10 * 1024 * 1024)))
app.config['RATE_LIMIT'] = os.environ.get('RATE_LIMIT', '30 per minute')
init_request_logging(app)

# Behind a reverse proxy (Render, Cloudflare) the client address arrives in
# X-Forwarded-For. Trust exactly as many hops as there are proxies, or the
# rate limiter keys every user to the proxy (too few) or lets clients spoof
# their address (too many).
PROXY_COUNT = int(os.environ.get('PROXY_COUNT', '0'))
if PROXY_COUNT:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=PROXY_COUNT, x_proto=PROXY_COUNT)

# The production build serves the frontend from this same origin, so CORS is
# only needed for the Vite dev server. Add origins explicitly when hosting the
# frontend elsewhere.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
    if o.strip()
]
CORS(app, origins=CORS_ORIGINS, expose_headers=['X-Request-ID'])

# gzip/brotli for the JS/CSS bundle and JSON responses
Compress(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)


@app.after_request
def cache_headers(response):
    # Vite puts a content hash in every asset filename, so assets can be cached
    # forever; index.html must always be revalidated to pick up a new build.
    if request.path.startswith('/assets/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    elif request.path in ('/', '/index.html'):
        response.headers['Cache-Control'] = 'no-cache'
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    return response


def _rate_limit():
    return app.config['RATE_LIMIT']


def _error(message, status):
    return jsonify(error=message), status


@app.errorhandler(HTTPException)
def http_error(exc):
    messages = {
        413: 'the upload is too large',
        429: 'too many requests, please slow down',
    }
    return _error(messages.get(exc.code, exc.description), exc.code)


@app.errorhandler(Exception)
def unexpected_error(exc):
    log.exception('unhandled error on %s', request.path)
    return _error('something went wrong on the server', 500)


def _json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _solve(expression):
    """Solve in the sandbox. Returns (result, error message or None)."""
    try:
        return sandbox.solve(expression), None
    except sandbox.SolveTimeout:
        log.info('solve timed out: %r', expression)
        return None, 'that took too long to solve'
    except sandbox.SolverBusy:
        return None, 'the server is busy, try again in a moment'


@app.route('/')
def index():
    if os.path.exists(os.path.join(STATIC_DIR, 'index.html')):
        return send_from_directory(STATIC_DIR, 'index.html')
    return "<h1>Equations Solver</h1>"


@app.route('/healthz')
@limiter.exempt
def healthz():
    """Liveness plus a real check: one model inference and one sandboxed solve."""
    try:
        healthcheck()
        result = sandbox.solve('1+1')
        ok = result.get('solution') == '2'
    except Exception:
        log.exception('health check failed')
        ok = False
    if not ok:
        return jsonify(status='unhealthy'), 503
    return jsonify(status='ok')


class _BadRequest(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def _read_image(read):
    """Decode the request's base64 'image' and run read() on it. Raises
    _BadRequest with the status to answer."""
    image_b64 = _json_body().get('image')
    if not image_b64:
        raise _BadRequest("missing 'image' field", 400)
    if not isinstance(image_b64, str):
        raise _BadRequest("'image' must be a base64 string", 400)

    try:
        image = BytesIO(base64.urlsafe_b64decode(image_b64))
    except (binascii.Error, ValueError):
        raise _BadRequest("'image' is not valid base64", 400) from None

    try:
        return read(image)
    except ImageTooLarge as exc:
        raise _BadRequest(str(exc), 413) from None
    except ValueError as exc:
        raise _BadRequest(str(exc), 422) from None
    except OSError:
        raise _BadRequest("could not decode the image (use PNG, JPEG or WebP)", 400) from None


def _characters(tokens):
    return [
        {
            'char': t['char'],
            'confidence': t['confidence'],
            'image': t['image'],
            'alternatives': [{'char': c, 'confidence': p} for c, p in t.get('alternatives', [])],
            'x': t['x'],
            'y': t['y'],
            'w': t['w'],
            'h': t['h'],
        }
        for t in tokens
    ]


@app.route('/predict', methods=['POST'])
@limiter.limit(_rate_limit)
def predict():
    try:
        tokens = _read_image(recognize)
    except _BadRequest as exc:
        return _error(str(exc), exc.status)

    if not tokens:
        return _error("no characters detected in the image", 422)

    return jsonify(characters=_characters(tokens), **_read_and_solve(tokens))


def _read_and_solve(tokens):
    """Read the 2D layout into an explicit expression, then solve it."""
    expression = build_expression(tokens)
    result, message = _solve(expression)
    solution = result['solution'] if result else None
    body = dict(
        recognized=result['expression'] if result else expression,
        formatted_equation=result['expression'] if result else expression,
        latex=result['latex'] if result else '',
        solution='' if solution is None else solution,
        solution_latex=result.get('solution_latex', '') if result else '',
        steps=result.get('steps', []) if result else [],
        solved=solution is not None,
    )
    if message:
        body['message'] = message
    return body


# symbols a corrected glyph may be set to: exactly what the model can emit
ALLOWED_GLYPHS = set(CODE2CHAR.values())
MAX_GLYPHS = 100
MAX_COORD = 100_000


def _valid_glyph(t):
    return (
        isinstance(t, dict)
        and t.get('char') in ALLOWED_GLYPHS
        and all(
            isinstance(t.get(k), int) and not isinstance(t.get(k), bool) and 0 <= t[k] <= MAX_COORD
            for k in ('x', 'y', 'w', 'h')
        )
    )


@app.route('/rebuild', methods=['POST'])
@limiter.limit(_rate_limit)
def rebuild():
    """Re-read glyphs after the user corrected some of them (tapping a tile
    and picking another symbol), keeping each glyph's position so powers,
    fractions and roots are still read from the layout."""
    glyphs = _json_body().get('characters')
    if not isinstance(glyphs, list) or not glyphs:
        return _error("missing 'characters' list", 400)
    if len(glyphs) > MAX_GLYPHS:
        return _error(f"too many characters (max {MAX_GLYPHS})", 400)
    if not all(_valid_glyph(t) for t in glyphs):
        return _error("each character needs a known 'char' and integer 'x', 'y', 'w', 'h'", 400)
    tokens = [{'char': t['char'], 'x': t['x'], 'y': t['y'], 'w': t['w'], 'h': t['h']} for t in glyphs]
    return jsonify(_read_and_solve(tokens))


@app.route('/solve', methods=['POST'])
@limiter.limit(_rate_limit)
def solve():
    expression = _json_body().get('expression')
    if expression is None or (isinstance(expression, str) and expression.strip() == ""):
        return _error("missing 'expression' field", 400)
    if not isinstance(expression, str):
        return _error("'expression' must be a string", 400)
    if len(expression) > MAX_LENGTH:
        return _error(f"expression is too long (max {MAX_LENGTH} characters)", 400)

    result, message = _solve(expression)
    if result is None:
        return jsonify(formatted_equation=expression.strip(), error=message), 422
    if result['solution'] is None:
        return jsonify(
            formatted_equation=result['expression'],
            error="could not solve that expression",
        ), 422

    return jsonify(
        formatted_equation=result['expression'],
        latex=result['latex'],
        solution=result['solution'],
        solution_latex=result.get('solution_latex', ''),
        steps=result.get('steps', []),
        solved=True,
    )


@app.route('/check', methods=['POST'])
@limiter.limit(_rate_limit)
def check():
    """Check a student's working, one equation per line: each line must keep
    the solutions of the line before. Takes typed 'lines' or a handwritten
    'image' of several lines. The answer is only included with 'reveal'."""
    body = _json_body()
    reveal = body.get('reveal') is True
    characters = None
    if 'image' in body:
        try:
            token_lines = _read_image(recognize_lines)
        except _BadRequest as exc:
            return _error(str(exc), exc.status)
        if not token_lines:
            return _error("no writing detected in the image", 422)
        if len(token_lines) > MAX_LINES:
            return _error(f"too many lines (max {MAX_LINES}); write one equation per line", 422)
        lines = [build_expression(tokens) for tokens in token_lines]
        characters = [_characters(tokens) for tokens in token_lines]
    else:
        lines = body.get('lines')
        if not isinstance(lines, list) or not lines:
            return _error("missing 'lines' list", 400)
        if len(lines) > MAX_LINES:
            return _error(f"too many lines (max {MAX_LINES})", 400)
        if not all(isinstance(line, str) and line.strip() for line in lines):
            return _error("each line must be a non-empty string", 400)
        if any(len(line) > MAX_LENGTH for line in lines):
            return _error(f"a line is too long (max {MAX_LENGTH} characters)", 400)

    try:
        result = sandbox.check(lines, reveal=reveal)
    except sandbox.SolveTimeout:
        log.info('check timed out: %r', lines)
        return _error('that took too long to check', 422)
    except sandbox.SolverBusy:
        return _error('the server is busy, try again in a moment', 503)
    except sandbox.SolverError:
        log.exception('check failed: %r', lines)
        return _error('could not check that working', 422)

    if characters is not None:
        for row, chars in zip(result['lines'], characters, strict=True):
            row['characters'] = chars
    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=os.environ.get('FLASK_DEBUG') == '1'
    )
