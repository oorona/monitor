"""Read canonical Oracle targets; run each SEPS login in an isolated Client process."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from suite_registry import Document

ALIAS = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
BUNDLE_FILES = ('cwallet.sso', 'ewallet.p12', 'tnsnames.ora', 'sqlnet.ora')


def load_oracle_targets():
    configured = os.environ.get('SUITE_REGISTRY_ROOT')
    if not configured:
        return []
    path = Path(configured) / 'databases.json'
    if path.is_symlink():
        raise ValueError('Shared registry must be a regular file')
    # An initialized empty registry has no document until its first database is added.
    if not path.exists():
        return []
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Shared registry exceeds size limit')
    document = Document.model_validate_json(path.read_text())
    targets = []
    for database in document.databases:
        access = database.access.get('monitor')
        if database.dialect != 'oracle' or not database.enabled or not access or not access.enabled:
            continue
        if access.mode != 'wallet':
            raise ValueError('Monitor Oracle access requires an external password-store wallet')
        targets.append(database)
    return targets


def wallet_directory(alias, root=None):
    if not isinstance(alias, str) or not ALIAS.fullmatch(alias):
        raise ValueError('Invalid Oracle wallet alias')
    root = Path(root or os.environ.get('ORACLE_WALLET_ROOT', '/wallets')).resolve(strict=True)
    wallet = (root / alias).resolve(strict=True)
    if not wallet.is_relative_to(root) or wallet == root:
        raise ValueError('Oracle wallet escapes its mounted directory')
    for name in BUNDLE_FILES:
        path = wallet / name
        if not path.is_file() or not path.resolve().is_relative_to(wallet):
            raise ValueError('Oracle wallet bundle is incomplete or contains an unsafe file')
    return wallet


def check_oracle(alias):
    try:
        wallet = wallet_directory(alias)
        # Client configuration is global per process. Isolate aliases so one wallet
        # cannot cause a later target to use another wallet's Oracle Net settings.
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('oracle_wallet_worker.py'))],
            input=json.dumps({'alias': alias, 'wallet_dir': str(wallet),
                             'client_lib_dir': os.environ.get('ORACLE_CLIENT_LIB_DIR')}),
            capture_output=True, text=True, timeout=8, check=False,
        )
        if result.returncode != 0:
            return False, 'Oracle wallet worker failed; check Client and wallet configuration'
        reply = json.loads(result.stdout)
        return reply['ok'], reply.get('error')
    except subprocess.TimeoutExpired:
        return False, 'Oracle wallet login exceeded 8 seconds'
    except (OSError, ValueError, KeyError):
        return False, 'Oracle wallet is unavailable or invalid; check the registered alias and mounted bundle'
