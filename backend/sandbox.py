"""Run SymPy work in separate, killable processes with a time limit.

Even with the allowlisted parser, ``solve`` on a legal input (a high-degree
polynomial, say) can run for minutes. Doing that inside the web worker would
block every other request, so each solve runs in a small pool of long-lived
helper processes. A job that overruns its time limit gets its process killed
and replaced, and the caller gets SolveTimeout instead of a hung request.

On Linux the helpers are forked from a forkserver that has already imported
SymPy, so replacing a killed helper takes milliseconds, and each helper gets
an address-space cap so a runaway job hits MemoryError instead of the host's
OOM killer. On Windows (local development) they are spawned and uncapped.
"""
import logging
import multiprocessing
import os
import queue
import sys
import threading

log = logging.getLogger(__name__)

SOLVE_TIMEOUT = float(os.environ.get('SOLVE_TIMEOUT', '3'))
POOL_SIZE = int(os.environ.get('SOLVER_PROCESSES', '2'))
# extra address space a helper may use beyond what it needs at startup
MEMORY_HEADROOM_MB = int(os.environ.get('SOLVER_MEMORY_MB', '256'))
# how long a request may wait for a free helper before giving up
QUEUE_TIMEOUT = float(os.environ.get('SOLVER_QUEUE_TIMEOUT', '10'))
# a freshly started helper must import SymPy before it can take work
STARTUP_TIMEOUT = 60.0


class SolveTimeout(Exception):
    """The job ran past its time limit and its process was killed."""


class SolverBusy(Exception):
    """Every helper stayed busy for longer than QUEUE_TIMEOUT."""


class SolverError(Exception):
    """The helper process died or could not be started."""


def _cap_memory(headroom_mb):
    try:
        import resource
        with open('/proc/self/statm') as f:
            pages = int(f.read().split()[0])
        current = pages * os.sysconf('SC_PAGE_SIZE')
        limit = current + headroom_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, OSError, ValueError):
        pass  # not Linux; rely on the time limit alone


def _helper_main(conn, headroom_mb):
    import calculator  # imported before the cap so startup never hits it
    _cap_memory(headroom_mb)
    conn.send('ready')
    while True:
        try:
            expression = conn.recv()
        except (EOFError, OSError):
            return
        try:
            result = calculator.solve_job(expression)
        except MemoryError:
            result = {'error': 'memory'}
        except Exception as exc:  # report, never let one input kill the helper
            result = {'error': f'{type(exc).__name__}: {exc}'}
        conn.send(result)


def _context():
    if sys.platform.startswith('linux'):
        ctx = multiprocessing.get_context('forkserver')
        ctx.set_forkserver_preload(['calculator'])
        return ctx
    return multiprocessing.get_context('spawn')


class _Helper:
    def __init__(self, ctx):
        self.conn, child = ctx.Pipe()
        self.process = ctx.Process(target=_helper_main, args=(child, MEMORY_HEADROOM_MB),
                                   daemon=True)
        self.process.start()
        child.close()
        self.ready = False

    def wait_ready(self):
        # poll in slices so a helper that crashes on startup fails fast
        # instead of holding the request for the whole startup timeout
        waited = 0.0
        while not self.ready and waited < STARTUP_TIMEOUT:
            if self.conn.poll(0.1):
                self.ready = self.conn.recv() == 'ready'
                break
            if not self.process.is_alive():
                break
            waited += 0.1
        return self.ready

    def kill(self):
        self.process.kill()
        self.process.join(timeout=5)
        self.conn.close()


class SolverPool:
    def __init__(self, size=POOL_SIZE, timeout=SOLVE_TIMEOUT):
        self.timeout = timeout
        self._ctx = _context()
        self._idle = queue.Queue()
        for _ in range(max(1, size)):
            self._idle.put(_Helper(self._ctx))

    def run(self, expression, timeout=None):
        """Return calculator.solve_job(expression) computed in a helper."""
        timeout = self.timeout if timeout is None else timeout
        try:
            helper = self._idle.get(timeout=QUEUE_TIMEOUT)
        except queue.Empty:
            raise SolverBusy() from None

        healthy = False
        try:
            if not helper.wait_ready():
                raise SolverError('solver process failed to start')
            helper.conn.send(expression)
            if not helper.conn.poll(timeout):
                raise SolveTimeout()
            result = helper.conn.recv()
            # after hitting its memory cap a helper may be left fragmented
            # or half-initialized; replace it rather than reuse it
            healthy = result.get('error') != 'memory'
        except (EOFError, OSError) as exc:
            raise SolverError('solver process died') from exc
        finally:
            if healthy:
                self._idle.put(helper)
            else:
                helper.kill()
                self._idle.put(_Helper(self._ctx))

        if 'error' in result:
            log.warning('solver failed on %r: %s', expression, result['error'])
            return {'expression': expression, 'solution': None, 'latex': ''}
        return result


_pool = None
_pool_pid = None
_pool_lock = threading.Lock()


def get_pool():
    """The process-wide pool, created on first use. Keyed by pid so a forked
    web worker never shares helpers (and their pipes) with its parent."""
    global _pool, _pool_pid
    with _pool_lock:
        if _pool is None or _pool_pid != os.getpid():
            _pool = SolverPool()
            _pool_pid = os.getpid()
        return _pool


def solve(expression):
    """Solve in the sandbox. Raises SolveTimeout, SolverBusy or SolverError."""
    return get_pool().run(expression)
