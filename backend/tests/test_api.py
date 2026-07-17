import base64
import io
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
