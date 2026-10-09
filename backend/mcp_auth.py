"""MCP bearer token custody; no Oracle database credentials are stored here."""
import argparse
import hashlib
import hmac
import os
from pathlib import Path
import secrets
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken


def token_path():
    return Path(os.environ.get('MONITOR_MCP_TOKEN_FILE', '/run/monitor-auth/token'))


def read_token(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256:
        raise ValueError('MCP token file is unavailable or invalid')
    value = path.read_text().strip()
    if not value.startswith('monitor_') or not 40 <= len(value) <= 200:
        raise ValueError('MCP token file is unavailable or invalid')
    return value


class MonitorTokenVerifier(TokenVerifier):
    async def verify_token(self, token):
        if not token or len(token) > 200:
            return None
        try:
            expected = read_token(token_path())
        except (OSError, ValueError):
            return None
        if not hmac.compare_digest(hashlib.sha256(token.encode()).digest(), hashlib.sha256(expected.encode()).digest()):
            return None
        return AccessToken(token=token, client_id='monitor-reader', scopes=['status:read'])


def initialize(destination, uid=None, gid=None):
    if destination.is_symlink():
        raise ValueError('MCP authentication directory must not be a symlink')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = destination / 'token'
    if path.exists() or path.is_symlink():
        read_token(path)  # Refuse an invalid existing key; never replace it silently.
        return
    value = 'monitor_' + secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(value + '\n')
    if uid is not None:
        os.chown(destination, uid, gid)
        os.chown(path, uid, gid)
    destination.chmod(0o700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path('/auth'))
    parser.add_argument('--uid', type=int)
    parser.add_argument('--gid', type=int)
    args = parser.parse_args()
    try:
        initialize(args.destination, args.uid, args.gid)
    except (OSError, ValueError):
        parser.exit(2, 'MCP token initialization failed; check directory permissions and existing token.\n')
    print('Monitor MCP token initialized; existing token preserved. Read its private file to configure the client.')


if __name__ == '__main__':
    main()
