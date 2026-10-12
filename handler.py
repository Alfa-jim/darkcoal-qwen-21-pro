"""RunPod queue adapter. No GPU work runs at import time."""
import atexit
import signal
import threading
from worker.request import validate_input
from worker.runtime import Supervisor
from worker.engine import EngineError

_supervisor = None
_lock = threading.Lock()


def handler(job):
    global _supervisor
    try:
        if not isinstance(job, dict):
            raise ValueError('job must be an object')
        value = validate_input(job.get('input'))
    except ValueError as exc:
        return {'error': str(exc)}
    with _lock:
        if _supervisor is None:
            _supervisor = Supervisor()
        try:
            _supervisor.ensure_started()
            return _supervisor.client.generate(value, job.get('id', 'image'))
        except (EngineError, RuntimeError, OSError, ValueError) as exc:
            _supervisor.stop()
            return {'error': str(exc)}


def main():
    global _supervisor
    _supervisor = Supervisor()
    atexit.register(_supervisor.stop)
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        _supervisor.ensure_started()
        import runpod
        runpod.serverless.start({'handler': handler})
    finally:
        _supervisor.stop()


if __name__ == '__main__':
    main()
