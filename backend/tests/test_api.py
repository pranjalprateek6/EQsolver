import base64
import io
from pathlib import Path

import pytest
from PIL import Image

import main
from app import app, limiter

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    limiter.reset()
    with app.test_client() as client:
        yield client


def encode_image(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def test_index(client):
    assert client.get('/').status_code == 200


def test_predict_recognizes_equation(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    response = client.post('/predict', json={'image': encode_image(image)})
    assert response.status_code == 200
    body = response.get_json()
    assert body['recognized']  # some expression was read
    assert 'solution' in body and 'solved' in body


def test_predict_returns_character_details(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    body = client.post('/predict', json={'image': encode_image(image)}).get_json()
    chars = body['characters']
    assert len(chars) >= 1
    for char in chars:
        assert set(char) == {'char', 'confidence', 'image'}
        assert 0.0 <= char['confidence'] <= 1.0
        assert char['image'].startswith('data:image/png;base64,')


def test_predict_missing_image_field(client):
    response = client.post('/predict', json={})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_predict_invalid_base64(client):
    response = client.post('/predict', json={'image': '!!!not-base64!!!'})
    assert response.status_code == 400


def test_predict_not_an_image(client):
    response = client.post('/predict', json={'image': encode_image(b'plain text')})
    assert response.status_code == 400


def test_predict_blank_image(client):
    buf = io.BytesIO()
    Image.new('RGB', (550, 300), 'white').save(buf, 'PNG')
    response = client.post('/predict', json={'image': encode_image(buf.getvalue())})
    assert response.status_code == 422
    assert 'no characters' in response.get_json()['error']


def test_solve_arithmetic(client):
    body = client.post('/solve', json={'expression': '8+3'}).get_json()
    assert body['solution'] == '11'
    assert body['solved'] is True


def test_solve_equation(client):
    response = client.post('/solve', json={'expression': 'x**(2)=4'})
    assert response.status_code == 200
    body = response.get_json()
    assert '2' in body['solution']


def test_solve_missing_expression(client):
    response = client.post('/solve', json={})
    assert response.status_code == 400


def test_solve_invalid_expression(client):
    response = client.post('/solve', json={'expression': '++'})
    assert response.status_code == 422


def png_bytes(width, height, color='white'):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buf, 'PNG')
    return buf.getvalue()


def test_solve_latex_is_as_written(client):
    body = client.post('/solve', json={'expression': '8+3'}).get_json()
    assert body['latex'] == '8 + 3'


def test_solve_implicit_multiplication(client):
    body = client.post('/solve', json={'expression': '2x+1=5'}).get_json()
    assert body['solution'] == '[2]'


# --- hardening -----------------------------------------------------------

@pytest.mark.parametrize('expression', [
    "__import__('os').system('echo pwned')",
    "x.__class__.__mro__",
    '9**9**9**9',
])
def test_solve_refuses_hostile_input(client, expression):
    response = client.post('/solve', json={'expression': expression})
    assert response.status_code == 422


def test_solve_timeout_is_422(client, monkeypatch):
    import sandbox

    def too_slow(expression):
        raise sandbox.SolveTimeout()
    monkeypatch.setattr(sandbox, 'solve', too_slow)
    response = client.post('/solve', json={'expression': 'x**2=4'})
    assert response.status_code == 422
    assert 'too long' in response.get_json()['error']


def test_predict_timeout_reports_unsolved(client, monkeypatch):
    import sandbox

    def too_slow(expression):
        raise sandbox.SolveTimeout()
    monkeypatch.setattr(sandbox, 'solve', too_slow)
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    body = client.post('/predict', json={'image': encode_image(image)}).get_json()
    assert body['solved'] is False
    assert 'too long' in body['message']


def test_solve_expression_too_long(client):
    response = client.post('/solve', json={'expression': '1+' * 500 + '1'})
    assert response.status_code == 400


@pytest.mark.parametrize('payload', [[1, 2], 'text', 5, None])
def test_non_object_json_body(client, payload):
    assert client.post('/solve', json=payload).status_code == 400
    assert client.post('/predict', json=payload).status_code == 400


def test_solve_expression_not_a_string(client):
    response = client.post('/solve', json={'expression': 5})
    assert response.status_code == 400


def test_predict_image_not_a_string(client):
    response = client.post('/predict', json={'image': {'a': 1}})
    assert response.status_code == 400


def test_predict_unsupported_format(client):
    buf = io.BytesIO()
    Image.new('RGB', (200, 100), 'white').save(buf, 'GIF')
    response = client.post('/predict', json={'image': encode_image(buf.getvalue())})
    assert response.status_code == 400


def test_predict_too_many_pixels(client, monkeypatch):
    monkeypatch.setattr(main, 'MAX_IMAGE_PIXELS', 1000)
    response = client.post('/predict', json={'image': encode_image(png_bytes(550, 300))})
    assert response.status_code == 413


@pytest.mark.parametrize('size', [(2000, 20), (100, 600), (10, 10)])
def test_predict_rejects_odd_shapes(client, size):
    response = client.post('/predict', json={'image': encode_image(png_bytes(*size))})
    assert response.status_code == 422


def test_request_body_too_large(client):
    previous = app.config['MAX_CONTENT_LENGTH']
    app.config['MAX_CONTENT_LENGTH'] = 1024
    try:
        response = client.post('/solve', json={'expression': 'x' * 5000})
    finally:
        app.config['MAX_CONTENT_LENGTH'] = previous
    assert response.status_code == 413
    assert 'error' in response.get_json()


def test_rate_limit(client):
    previous = app.config['RATE_LIMIT']
    app.config['RATE_LIMIT'] = '2 per minute'
    try:
        codes = [client.post('/solve', json={'expression': '1+1'}).status_code for _ in range(3)]
    finally:
        app.config['RATE_LIMIT'] = previous
    assert codes == [200, 200, 429]


def test_healthz(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}


def test_cors_only_for_allowed_origins(client):
    allowed = client.post('/solve', json={'expression': '1+1'},
                          headers={'Origin': 'http://localhost:3000'})
    assert allowed.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'
    other = client.post('/solve', json={'expression': '1+1'},
                        headers={'Origin': 'https://evil.example'})
    assert 'Access-Control-Allow-Origin' not in other.headers


def test_unknown_route_is_json_404(client):
    response = client.get('/no-such-thing')
    assert response.status_code == 404
    assert 'error' in response.get_json()
