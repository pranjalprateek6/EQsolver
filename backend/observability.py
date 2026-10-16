"""Logging, request ids and optional error tracking.

Every log line is one JSON object (set LOG_FORMAT=text for a readable local
console), and each request gets an id: the caller's X-Request-ID when it
sends a sane one, else a fresh one. The id is returned in X-Request-ID, put on
every log line written while handling the request and attached to Sentry
events, so a user's error report can be matched to the server logs.

Sentry is enabled only when SENTRY_DSN is set. Requests carry handwriting
images, so request bodies, cookies, user details and stack-frame locals (which
hold the decoded image) are never sent; expressions in log messages are fine.
"""
import json
import logging
import os
import re
import time
import uuid

from flask import g, has_request_context, request

log = logging.getLogger('eqsolver')

REQUEST_ID_HEADER = 'X-Request-ID'
# accept an upstream id only if it is short and plain, so it is safe to log
# and echo back
_REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

# LogRecord attributes that are not extra fields passed by the caller
_RESERVED = set(vars(logging.LogRecord('', 0, '', 0, '', (), None))) | {'message', 'asctime'}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S') + f'.{int(record.msecs):03d}Z',
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _RESERVED})
        if record.exc_info:
            entry['exc'] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


JsonFormatter.converter = time.gmtime


class RequestIdFilter(logging.Filter):
    """Stamp the current request's id on every record logged during it."""

    def filter(self, record):
        if not hasattr(record, 'request_id') and has_request_context():
            record.request_id = g.get('request_id')
        return True


def configure_logging():
    handler = logging.StreamHandler()
    if os.environ.get('LOG_FORMAT', 'json').lower() == 'text':
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    else:
        handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
    # our own request log replaces werkzeug's dev-server access lines
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def init_request_logging(app):
    @app.before_request
    def start_request():
        incoming = request.headers.get(REQUEST_ID_HEADER, '')
        g.request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        g.request_start = time.perf_counter()
        _sentry_tag('request_id', g.request_id)

    @app.after_request
    def finish_request(response):
        request_id = g.get('request_id')
        if request_id:
            response.headers[REQUEST_ID_HEADER] = request_id
        start = g.get('request_start')
        # the host polls /healthz every few seconds; only log it when it fails
        if start is None or (request.path == '/healthz' and response.status_code < 400):
            return response
        # no query string or body: they can carry user input and images
        log.info('request', extra={
            'method': request.method,
            'path': request.path,
            'endpoint': request.endpoint,
            'status': response.status_code,
            'latency_ms': round((time.perf_counter() - start) * 1000, 1),
            'bytes_in': request.content_length,
        })
        return response


_sentry_enabled = False


def _sentry_tag(key, value):
    if _sentry_enabled:
        import sentry_sdk
        sentry_sdk.set_tag(key, value)


def _scrub_event(event, hint):
    """Last line of defence before anything leaves for Sentry: drop request
    bodies, cookies and headers, and blank any string that looks like image
    data wherever it ended up."""
    req = event.get('request')
    if req:
        for key in ('data', 'cookies', 'headers', 'query_string', 'env'):
            req.pop(key, None)
    event.pop('user', None)
    return _strip_images(event)


def _strip_images(value):
    if isinstance(value, dict):
        return {k: ('[removed]' if k == 'image' else _strip_images(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_images(v) for v in value]
    if isinstance(value, str) and (value.startswith('data:image') or len(value) > 2048):
        return '[removed]'
    return value


def init_sentry():
    """Turn on Sentry if SENTRY_DSN is set. Returns whether it is on."""
    global _sentry_enabled
    dsn = os.environ.get('SENTRY_DSN')
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        # Render sets IS_PULL_REQUEST on pull request previews
        environment=os.environ.get('SENTRY_ENVIRONMENT')
        or ('preview' if os.environ.get('IS_PULL_REQUEST') == 'true' else 'production'),
        # Render sets RENDER_GIT_COMMIT on every deploy
        release=os.environ.get('SENTRY_RELEASE') or os.environ.get('RENDER_GIT_COMMIT'),
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0')),
        # no user details, no request bodies, no frame locals (they hold the
        # decoded image)
        data_collection={'user_info': False, 'http_bodies': [], 'stack_frame_variables': False},
        before_send=_scrub_event,
        before_send_transaction=_scrub_event,
    )
    _sentry_enabled = True
    log.info('sentry enabled')
    return True
