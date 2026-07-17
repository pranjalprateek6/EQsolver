import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from app import app

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def encode_image(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def test_index(client):
    response = client.get('/')
    assert response.status_code == 200


def test_predict_recognizes_equation(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    response = client.post('/predict', json={'image': encode_image(image)})
    assert response.status_code == 200
    body = response.get_json()
    assert body['recognized'] == '8+3'
    assert body['formatted_equation'] == '8+3'
    assert body['solution'] == '11'
    assert body['solved'] is True


def test_predict_returns_character_details(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    response = client.post('/predict', json={'image': encode_image(image)})
    body = response.get_json()
    chars = body['characters']
    assert len(chars) == 3
    for char in chars:
        assert set(char) == {'raw', 'char', 'confidence', 'image'}
        assert 0.0 <= char['confidence'] <= 1.0
        assert char['image'].startswith('data:image/png;base64,')
    # the human symbols concatenate to the recognized string
    assert ''.join(c['char'] for c in chars) == body['recognized']


def test_predict_missing_image_field(client):
    response = client.post('/predict', json={})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_predict_invalid_base64(client):
    response = client.post('/predict', json={'image': '!!!not-base64!!!'})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_predict_not_an_image(client):
    response = client.post('/predict', json={'image': encode_image(b'plain text')})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_predict_blank_image(client):
    buf = io.BytesIO()
    Image.new('RGB', (550, 300), 'white').save(buf, 'PNG')
    response = client.post('/predict', json={'image': encode_image(buf.getvalue())})
    assert response.status_code == 422
    assert 'no characters' in response.get_json()['error']


def test_predict_transparent_image_is_flattened(client):
    # a fully transparent canvas should read as blank, not crash
    buf = io.BytesIO()
    Image.new('RGBA', (550, 300), (0, 0, 0, 0)).save(buf, 'PNG')
    response = client.post('/predict', json={'image': encode_image(buf.getvalue())})
    assert response.status_code == 422


def test_solve_arithmetic(client):
    response = client.post('/solve', json={'expression': '8+3'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['solution'] == '11'
    assert body['solved'] is True


def test_solve_equation(client):
    response = client.post('/solve', json={'expression': 'x2=4'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['formatted_equation'] == 'x**2=4'
    # solutions come back as a stringified list
    assert '2' in body['solution']


def test_solve_missing_expression(client):
    response = client.post('/solve', json={})
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_solve_invalid_expression(client):
    response = client.post('/solve', json={'expression': '++'})
    assert response.status_code == 422
    assert 'error' in response.get_json()
