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
        assert set(char) == {'char', 'confidence', 'image', 'alternatives', 'x', 'y', 'w', 'h'}
        assert 0.0 <= char['confidence'] <= 1.0
        assert 1 <= len(char['alternatives']) <= 3
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


def test_solve_returns_solution_latex(client):
    body = client.post('/solve', json={'expression': 'y**2=9'}).get_json()
    assert body['solution_latex'] == 'y = -3, 3'


def test_predict_returns_solution_latex(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    body = client.post('/predict', json={'image': encode_image(image)}).get_json()
    assert 'solution_latex' in body


def test_assets_are_cached_forever_and_index_is_revalidated(client, tmp_path, monkeypatch):
    import app as app_module

    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets' / 'index-abc123.js').write_text('console.log(1)')
    (tmp_path / 'index.html').write_text('<div id="root"></div>')
    monkeypatch.setattr(app_module, 'STATIC_DIR', str(tmp_path))
    monkeypatch.setattr(app, 'static_folder', str(tmp_path))
    asset = client.get('/assets/index-abc123.js')
    assert asset.status_code == 200
    assert 'immutable' in asset.headers['Cache-Control']
    assert client.get('/').headers['Cache-Control'] == 'no-cache'


def test_json_is_compressed_when_asked(client):
    response = client.post(
        '/solve', json={'expression': '1+' * 140 + '1'}, headers={'Accept-Encoding': 'gzip'}
    )
    assert response.headers.get('Content-Encoding') == 'gzip'


def test_solve_latex_is_as_written(client):
    body = client.post('/solve', json={'expression': '8+3'}).get_json()
    assert body['latex'] == '8 + 3'


def test_solve_implicit_multiplication(client):
    body = client.post('/solve', json={'expression': '2x+1=5'}).get_json()
    assert body['solution'] == '[2]'


# --- hardening -----------------------------------------------------------


@pytest.mark.parametrize(
    'expression',
    [
        "__import__('os').system('echo pwned')",
        "x.__class__.__mro__",
        '9**9**9**9',
    ],
)
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
    allowed = client.post('/solve', json={'expression': '1+1'}, headers={'Origin': 'http://localhost:3000'})
    assert allowed.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'
    other = client.post('/solve', json={'expression': '1+1'}, headers={'Origin': 'https://evil.example'})
    assert 'Access-Control-Allow-Origin' not in other.headers


def test_unknown_route_is_json_404(client):
    response = client.get('/no-such-thing')
    assert response.status_code == 404
    assert 'error' in response.get_json()


# --- tap-to-correct ------------------------------------------------------


def _glyph(char, x, y=100, w=28, h=40):
    return {'char': char, 'x': x, 'y': y, 'w': w, 'h': h}


def test_rebuild_reads_corrected_glyphs(client):
    glyphs = [_glyph('8', 0), _glyph('+', 40), _glyph('3', 80)]
    body = client.post('/rebuild', json={'characters': glyphs}).get_json()
    assert body['recognized'] == '8+3'
    assert body['solution'] == '11'
    assert body['solved'] is True


def test_rebuild_keeps_layout(client):
    glyphs = [_glyph('x', 0), _glyph('2', 34, y=80, w=16, h=24), _glyph('=', 70), _glyph('9', 110)]
    body = client.post('/rebuild', json={'characters': glyphs}).get_json()
    assert body['recognized'] == 'x**(2)=9'
    assert body['solution_latex'] == 'x = -3, 3'


def test_predict_glyphs_round_trip_through_rebuild(client):
    image = (FIXTURES / 'eight_plus_three.png').read_bytes()
    predicted = client.post('/predict', json={'image': encode_image(image)}).get_json()
    rebuilt = client.post('/rebuild', json={'characters': predicted['characters']}).get_json()
    assert rebuilt['recognized'] == predicted['recognized']


@pytest.mark.parametrize(
    'glyphs',
    [
        None,
        [],
        'abc',
        [{'char': 'a', 'x': 0, 'y': 0, 'w': 1, 'h': 1}],
        [{'char': '__import__', 'x': 0, 'y': 0, 'w': 1, 'h': 1}],
        [{'char': '1', 'x': '0', 'y': 0, 'w': 1, 'h': 1}],
        [{'char': '1', 'x': -5, 'y': 0, 'w': 1, 'h': 1}],
        [{'char': '1', 'x': True, 'y': 0, 'w': 1, 'h': 1}],
        [{'char': '1', 'x': 0, 'y': 0, 'w': 1, 'h': 1}] * 101,
    ],
)
def test_rebuild_rejects_bad_input(client, glyphs):
    assert client.post('/rebuild', json={'characters': glyphs}).status_code == 400


def test_solve_returns_steps(client):
    body = client.post('/solve', json={'expression': '2x+1=5'}).get_json()
    assert body['steps'][0] == {'title': 'Start with the equation', 'latex': '2 x + 1 = 5'}
    assert body['steps'][-1]['latex'] == 'x = 2'


def test_arithmetic_has_no_steps(client):
    assert client.post('/solve', json={'expression': '8+3'}).get_json()['steps'] == []


# --- /check: checking a student's working line by line ---


def test_check_typed_lines(client):
    response = client.post('/check', json={'lines': ['2x+3=11', '2x=11+3', 'x=7']})
    assert response.status_code == 200
    body = response.get_json()
    assert [row['ok'] for row in body['lines']] == [True, False, True]
    assert body['first_error'] == 1
    assert 'sign' in body['lines'][1]['reason']
    assert body['lines'][0]['latex'] == '2 x + 3 = 11'
    assert body['finished'] is False
    assert 'answer_latex' not in body  # the answer is only given when asked


def test_check_correct_working_is_finished(client):
    body = client.post('/check', json={'lines': ['2x+3=11', '2x=8', 'x=4']}).get_json()
    assert body['first_error'] is None and body['finished'] is True


def test_check_reveal(client):
    body = client.post('/check', json={'lines': ['2x+3=11'], 'reveal': True}).get_json()
    assert body['answer_latex'] == 'x = 4'


@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'lines': []},
        {'lines': 'x=1'},
        {'lines': ['x=1', 5]},
        {'lines': ['x=1', '   ']},
        {'lines': ['x=1'] * 13},
        {'lines': ['1+' * 200 + '1']},
    ],
)
def test_check_rejects_bad_input(client, payload):
    assert client.post('/check', json=payload).status_code == 400


def test_check_hostile_line_is_not_run(client):
    body = client.post('/check', json={'lines': ['x=1', "__import__('os').system('id')"]}).get_json()
    assert body['lines'][1]['ok'] is False


def test_check_timeout_is_422(client, monkeypatch):
    import sandbox

    def too_slow(lines, reveal=False):
        raise sandbox.SolveTimeout()

    monkeypatch.setattr(sandbox, 'check', too_slow)
    response = client.post('/check', json={'lines': ['x=1', 'x=1']})
    assert response.status_code == 422
    assert 'too long' in response.get_json()['error']


def _stacked(image_bytes, copies=2, gap=None):
    """The fixture equation written on several lines, like a page of working."""
    line = main._flatten_transparency(Image.open(io.BytesIO(image_bytes))).convert('L')
    gap = gap if gap is not None else line.height
    page = Image.new('L', (line.width, copies * line.height + (copies - 1) * gap), 255)
    for i in range(copies):
        page.paste(line, (0, i * (line.height + gap)))
    buf = io.BytesIO()
    page.save(buf, 'PNG')
    return buf.getvalue()


def test_check_handwritten_lines(client):
    single = client.post(
        '/predict', json={'image': encode_image((FIXTURES / 'eight_plus_three.png').read_bytes())}
    ).get_json()
    image = _stacked((FIXTURES / 'eight_plus_three.png').read_bytes())
    response = client.post('/check', json={'image': encode_image(image)})
    assert response.status_code == 200
    body = response.get_json()
    assert len(body['lines']) == 2
    # each line is read just like the same equation on its own
    for row in body['lines']:
        assert row['text'] == single['recognized']
        assert [c['char'] for c in row['characters']] == [c['char'] for c in single['characters']]
    assert body['lines'][1]['characters'][0]['y'] > body['lines'][0]['characters'][0]['y']


def test_check_handwritten_rejects_bad_images(client):
    assert client.post('/check', json={'image': 'not base64!!'}).status_code == 400
    assert client.post('/check', json={'image': 5}).status_code == 400
    blank = io.BytesIO()
    Image.new('L', (200, 200), 255).save(blank, 'PNG')
    assert client.post('/check', json={'image': encode_image(blank.getvalue())}).status_code == 422
