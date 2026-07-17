import base64
import binascii
from io import BytesIO

from flask import Flask, jsonify, request
from flask_cors import CORS

from calculator import solve_text, substitute
from main import recognize

app = Flask(__name__)
CORS(app)


@app.route('/')
def index():
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
        characters = recognize(image)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    except OSError:
        return jsonify(error="could not decode the image data"), 400

    if not characters:
        return jsonify(error="no characters detected in the image"), 422

    # attach the human-readable symbol for each glyph (t -> +, S -> = ...)
    for char in characters:
        char['char'] = substitute(char['raw'])

    recognized = "".join(char['char'] for char in characters)
    formatted_equation, solution = solve_text(recognized)

    return jsonify(
        characters=characters,
        recognized=recognized,
        formatted_equation=formatted_equation,
        solution="" if solution is None else str(solution),
        solved=solution is not None,
    )


@app.route('/solve', methods=['POST'])
def solve():
    body = request.get_json(silent=True) or {}
    expression = body.get('expression')
    if expression is None or expression.strip() == "":
        return jsonify(error="missing 'expression' field"), 400

    formatted_equation, solution = solve_text(expression.strip())
    if solution is None:
        return jsonify(
            formatted_equation=formatted_equation,
            error="could not solve that expression",
        ), 422

    return jsonify(
        formatted_equation=formatted_equation,
        solution=str(solution),
        solved=True,
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
