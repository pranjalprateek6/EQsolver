import base64
import binascii
import os
from io import BytesIO

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from calculator import solve_expression, to_latex
from main import recognize
from structure import build_expression

# in a production build the compiled frontend is copied here and served by Flask
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
CORS(app)


def _solution_str(solution):
    return "" if solution is None else str(solution)


@app.route('/')
def index():
    if os.path.exists(os.path.join(STATIC_DIR, 'index.html')):
        return send_from_directory(STATIC_DIR, 'index.html')
    return "<h1>Equations Solver</h1>"


@app.route('/predict', methods=['POST'])
def predict():
    body = request.get_json(silent=True) or {}
    image_b64 = body.get('image')
    if not image_b64:
        return jsonify(error="missing 'image' field"), 400

    try:
        image = BytesIO(base64.urlsafe_b64decode(image_b64))
    except (binascii.Error, ValueError):
        return jsonify(error="'image' is not valid base64"), 400

    try:
        tokens = recognize(image)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    except OSError:
        return jsonify(error="could not decode the image data"), 400

    if not tokens:
        return jsonify(error="no characters detected in the image"), 422

    # read the 2D layout into an explicit expression, then solve it
    expression = build_expression(tokens)
    expression, solution = solve_expression(expression)

    characters = [
        {'char': t['char'], 'confidence': t['confidence'], 'image': t['image']}
        for t in tokens
    ]
    return jsonify(
        characters=characters,
        recognized=expression,
        formatted_equation=expression,
        latex=to_latex(expression),
        solution=_solution_str(solution),
        solved=solution is not None,
    )


@app.route('/solve', methods=['POST'])
def solve():
    body = request.get_json(silent=True) or {}
    expression = body.get('expression')
    if expression is None or expression.strip() == "":
        return jsonify(error="missing 'expression' field"), 400

    expression, solution = solve_expression(expression)
    if solution is None:
        return jsonify(
            formatted_equation=expression,
            error="could not solve that expression",
        ), 422

    return jsonify(
        formatted_equation=expression,
        latex=to_latex(expression),
        solution=str(solution),
        solved=True,
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
