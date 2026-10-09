"""Read canonical Oracle targets; run each shared wallet login in an isolated Client process."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from suite_registry import Document
from shared_wallet import BUNDLE_FILES, SharedWalletError, entries, resolve_wallet

ALIAS = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')



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
    root = Path(root or os.environ.get('ORACLE_WALLET_ROOT', '/wallets'))
    wallet = resolve_wallet(root, alias)
    entry = entries(wallet)[alias]
    if entry["account"].upper() in {"SYS", "SYSTEM"} or entry["privilege"] != "normal":
        raise SharedWalletError("Monitor requires an ordinary account entry in the shared wallet")
    return wallet


def check_oracle(alias):
    try:
        wallet = wallet_directory(alias)
        # Pin the same shared wallet snapshot for configuration and password retrieval.
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
