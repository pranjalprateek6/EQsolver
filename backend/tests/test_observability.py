import base64
import json
import logging

import pytest

import observability
from app import app, limiter


@pytest.fixture()
def client():
    app.config['TESTING'] = True
    limiter.reset()
    with app.test_client() as client:
        yield client


@pytest.fixture()
def request_logs(caplog):
    caplog.set_level(logging.INFO, logger='eqsolver')
    return lambda: [r for r in caplog.records if r.getMessage() == 'request']


def test_request_id_is_generated(client):
    response = client.post('/solve', json={'expression': '1+1'})
    assert len(response.headers['X-Request-ID']) == 32


def test_request_id_is_echoed(client):
    response = client.post('/solve', json={'expression': '1+1'},
                           headers={'X-Request-ID': 'abc-123'})
    assert response.headers['X-Request-ID'] == 'abc-123'


def test_unsafe_request_id_is_replaced(client):
    unsafe = '<script>' + 'x' * 200
    response = client.post('/solve', json={'expression': '1+1'},
                           headers={'X-Request-ID': unsafe})
    assert len(response.headers['X-Request-ID']) == 32


def test_request_is_logged(client, request_logs):
    client.post('/solve', json={'expression': '1+1'}, headers={'X-Request-ID': 'req-1'})
    [record] = request_logs()
    assert record.request_id == 'req-1'
    assert record.endpoint == 'solve'
    assert record.path == '/solve'
    assert record.status == 200
    assert record.latency_ms >= 0


def test_request_log_has_no_image_data(client, request_logs):
    client.post('/predict', json={'image': 'aGVsbG8gd29ybGQ='})
    [record] = request_logs()
    assert record.status == 400
    assert 'aGVsbG8gd29ybGQ' not in json.dumps(vars(record), default=str)


def test_healthy_healthz_is_not_logged(client, request_logs):
    client.get('/healthz')
    assert request_logs() == []


def test_json_formatter_includes_extras():
    record = logging.LogRecord('eqsolver', logging.INFO, __file__, 1, 'request', (), None)
    record.request_id = 'r1'
    record.status = 200
    line = json.loads(observability.JsonFormatter().format(record))
    assert line['msg'] == 'request'
    assert line['level'] == 'INFO'
    assert line['request_id'] == 'r1'
    assert line['status'] == 200
    assert line['ts'].endswith('Z')


def test_sentry_is_off_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    assert observability.init_sentry() is False


def test_sentry_scrubber_drops_bodies_and_images():
    event = {
        'request': {'url': 'https://x/predict', 'method': 'POST',
                    'data': {'image': 'iVBORw0KGgo'}, 'headers': {'Cookie': 'c'}},
        'user': {'ip_address': '1.2.3.4'},
        'extra': {'image': 'abc', 'expression': 'x+1=2',
                  'tile': 'data:image/png;base64,iVBORw0KGgo', 'blob': 'A' * 5000},
    }
    scrubbed = observability._scrub_event(event, {})
    assert scrubbed['request'] == {'url': 'https://x/predict', 'method': 'POST'}
    assert 'user' not in scrubbed
    assert scrubbed['extra'] == {'image': '[removed]', 'expression': 'x+1=2',
                                 'tile': '[removed]', 'blob': '[removed]'}


def test_sentry_event_never_carries_the_image(client, monkeypatch):
    """With Sentry on, a crash while reading an upload reports the error but
    none of the request body."""
    import sentry_sdk
    from sentry_sdk.transport import Transport

    sent = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            sent.extend(item.payload.json for item in envelope.items if item.payload.json)

    monkeypatch.setenv('SENTRY_DSN', 'https://key@o0.ingest.sentry.io/0')
    real_init = sentry_sdk.init
    monkeypatch.setattr(sentry_sdk, 'init', lambda **kw: real_init(transport=Capture, **kw))
    monkeypatch.setattr(observability, '_sentry_enabled', False)
    marker = 'SECRET' + 'PIXELS'  # built here so the test's own source never contains it
    image = base64.b64encode(marker.encode() * 40).decode()

    def boom(_image):
        raise RuntimeError('model exploded')

    monkeypatch.setattr('app.recognize', boom)
    try:
        assert observability.init_sentry()
        # the Flask integration hooks app instances on creation; this one
        # exists already, so report through the logging integration it uses
        response = client.post('/predict', json={'image': image})
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # no DSN: switch it off again
    assert response.status_code == 500
    assert sent, 'no event was sent'
    dumped = json.dumps(sent)
    assert 'model exploded' in dumped
    assert image[:40] not in dumped and marker not in dumped
