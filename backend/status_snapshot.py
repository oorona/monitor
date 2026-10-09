"""One completed poll, published atomically to the dashboard and MCP tools."""
from datetime import UTC, datetime
import os
from threading import Lock

_lock = Lock()
_state = {'status': {}, 'updated_at': None, 'last_attempt_at': None, 'poll_error': False}


def begin_poll():
    with _lock:
        _state['last_attempt_at'] = datetime.now(UTC)


def publish(status):
    with _lock:
        _state.update(status=status, updated_at=datetime.now(UTC), poll_error=False)


def fail_poll():
    with _lock:
        _state['poll_error'] = True


def get_snapshot():
    with _lock:
        state = dict(_state)
    updated = state['updated_at']
    age = max(0, (datetime.now(UTC) - updated).total_seconds()) if updated else None
    stale_after = max(120, 2 * max(1, int(os.environ.get('MONITOR_POLL_INTERVAL', '60'))))
    freshness = 'initializing' if updated is None else 'stale' if state['poll_error'] or age > stale_after else 'current'
    return {'status': state['status'], 'metadata': {
        'state': freshness, 'updated_at': updated.isoformat() if updated else None,
        'last_attempt_at': state['last_attempt_at'].isoformat() if state['last_attempt_at'] else None,
        'age_seconds': round(age, 1) if age is not None else None,
        'stale_after_seconds': stale_after, 'poll_error': state['poll_error'],
    }}
