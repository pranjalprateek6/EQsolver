import base64
import binascii
import logging
import os
from io import BytesIO

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

import sandbox
from main import ImageTooLarge, healthcheck, recognize
from safe_parse import MAX_LENGTH
from structure import build_expression

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO'),
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('eqsolver')

# in a production build the compiled frontend is copied here and served by Flask
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
# a base64 phone photo is about 4/3 of the file size; refuse anything bigger
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_REQUEST_BYTES', str(10 * 1024 * 1024)))
app.config['RATE_LIMIT'] = os.environ.get('RATE_LIMIT', '30 per minute')

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
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    'CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if o.strip()]
CORS(app, origins=CORS_ORIGINS)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)


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


@app.route('/predict', methods=['POST'])
@limiter.limit(_rate_limit)
def predict():
    image_b64 = _json_body().get('image')
    if not image_b64:
        return _error("missing 'image' field", 400)
    if not isinstance(image_b64, str):
        return _error("'image' must be a base64 string", 400)

    try:
        image = BytesIO(base64.urlsafe_b64decode(image_b64))
    except (binascii.Error, ValueError):
        return _error("'image' is not valid base64", 400)

    try:
        tokens = recognize(image)
    except ImageTooLarge as exc:
        return _error(str(exc), 413)
    except ValueError as exc:
        return _error(str(exc), 422)
    except OSError:
        return _error("could not decode the image (use PNG, JPEG or WebP)", 400)

    if not tokens:
        return _error("no characters detected in the image", 422)

    # read the 2D layout into an explicit expression, then solve it
    expression = build_expression(tokens)
    result, message = _solve(expression)
    solution = result['solution'] if result else None

    characters = [
        {'char': t['char'], 'confidence': t['confidence'], 'image': t['image']}
        for t in tokens
    ]
    body = dict(
        characters=characters,
        recognized=result['expression'] if result else expression,
        formatted_equation=result['expression'] if result else expression,
        latex=result['latex'] if result else '',
        solution='' if solution is None else solution,
        solved=solution is not None,
    )
    if message:
        body['message'] = message
    return jsonify(body)


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
        solved=True,
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')),
            debug=os.environ.get('FLASK_DEBUG') == '1')
