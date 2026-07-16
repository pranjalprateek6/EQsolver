import base64
import binascii
from io import BytesIO

from flask import Flask, jsonify, request
from flask_cors import CORS

from calculator import calculate
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
        equation = recognize(image)
    except ValueError as exc:
        return jsonify(error=str(exc)), 422
    except OSError:
        return jsonify(error="could not decode the image data"), 400

    if not equation:
        return jsonify(error="no characters detected in the image"), 422

    formatted_equation, solution = calculate(equation)
    if solution is None:
        return jsonify(
            entered_equation=equation,
            formatted_equation=formatted_equation,
            error="could not solve the recognized expression",
        ), 422

    return jsonify(
        entered_equation=equation,
        formatted_equation=formatted_equation,
        solution=str(solution),
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
