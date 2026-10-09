#!/usr/bin/env python3
"""Configuration shared by the poller and portable configuration bundles."""
import os
import re
from pathlib import Path
import yaml

SECRET_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")

def validate_config(config):
    if not isinstance(config, dict) or not isinstance(config.get('servers'), dict):
        raise ValueError('Configuration requires a servers mapping')
    secrets = set()
    for kind, environments in config['servers'].items():
        if kind not in ('database', 'application') or not isinstance(environments, dict):
            raise ValueError('Unsupported server group')
        for servers in environments.values():
            if not isinstance(servers, dict):
                raise ValueError('Environment requires a server mapping')
            for entries in servers.values():
                if not isinstance(entries, dict):
                    raise ValueError('Server requires a mapping')
                if kind == 'database':
                    for details in entries.values():
                        if not isinstance(details, dict) or details.get('type', 'ora') not in ('ora', 'pg', 'mysql'):
                            raise ValueError('Unsupported database definition')
                        name = details.get('password')
                        if not isinstance(name, str) or not SECRET_NAME.fullmatch(name):
                            raise ValueError('Database password must reference a safe secret name')
                        if not isinstance(details.get('username'), str):
                            raise ValueError('Database username is required')
                        if 'port' in details and (type(details['port']) is not int or not 1 <= details['port'] <= 65535):
                            raise ValueError('Invalid database port')
                        secrets.add(name)
                else:
                    urls = entries.get('urls', [])
                    if not isinstance(urls, list):
                        raise ValueError('Application urls must be a list')
                    urls = [*urls, *([entries['url']] if 'url' in entries else [])]
                    if any(not isinstance(url, str) or not url.startswith(('http://', 'https://')) for url in urls):
                        raise ValueError('Application URLs must use HTTP or HTTPS')
    return secrets

def get_secret(secret_name, default=None):
    if not isinstance(secret_name, str) or not SECRET_NAME.fullmatch(secret_name):
        return default
    root = Path(os.environ.get('MONITOR_SECRETS_PATH', '/run/secrets'))
    try:
        return (root / secret_name).read_text().strip()
    except OSError:
        try:
            return (root / f'{secret_name}.txt').read_text().strip()
        except OSError:
            return os.environ.get(secret_name.upper(), default)

def load_config(config_path=None):
    configured = config_path or os.environ.get('MONITOR_CONFIG_PATH')
    if configured:
        path = Path(configured)
    else:
        path = next((p for p in (Path('../servers.yaml'), Path('servers.yaml')) if p.is_file()), Path('servers.yaml'))
    config = yaml.safe_load(path.read_text())
    validate_config(config)
    return config

"""Offline configuration transfer. Archives contain credentials; keep them private."""
import argparse
from contextlib import nullcontext
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
import yaml

MAX_BYTES = 16 * 1024 * 1024
EMPTY_CONFIG = b'servers:\n  database: {}\n  application: {}\n'

def read_bundle(archive):
    files = {}
    total = 0
    with tarfile.open(fileobj=archive, mode='r|gz') as tar:
        for member in tar:
            name = member.name
            allowed = name in ('manifest.json', 'servers.yaml') or (name.startswith('secrets/') and len(Path(name).parts) == 2)
            if not member.isfile() or not allowed or name in files or '..' in Path(name).parts:
                raise ValueError('Unsafe or duplicate bundle entry')
            total += member.size
            if total > MAX_BYTES or len(files) >= 1000:
                raise ValueError('Bundle exceeds transfer limits')
            files[name] = tar.extractfile(member).read()
    manifest = json.loads(files.pop('manifest.json'))
    if manifest.get('version') != 1 or not isinstance(manifest.get('sha256'), dict):
        raise ValueError('Unsupported bundle manifest')
    if {name: hashlib.sha256(value).hexdigest() for name, value in files.items()} != manifest['sha256']:
        raise ValueError('Bundle checksum mismatch')
    required = validate_config(yaml.safe_load(files['servers.yaml']))
    if {f'secrets/{name}' for name in required} != set(files) - {'servers.yaml'}:
        raise ValueError('Bundle secret references do not match its files')
    if any(not files[f'secrets/{name}'].strip() for name in required):
        raise ValueError('Bundle contains an empty secret')
    return files

def export_bundle(config_path, secrets_path, output):
    config_bytes = config_path.read_bytes()
    required = validate_config(yaml.safe_load(config_bytes))
    files = {'servers.yaml': config_bytes}
    for name in sorted(required):
        candidates = (secrets_path / name, secrets_path / f'{name}.txt')
        source = next((p for p in candidates if p.is_file()), None)
        value = source.read_bytes() if source else os.environ.get(name.upper(), '').encode()
        if not value.strip():
            raise ValueError(f'Missing referenced secret: {name}')
        files[f'secrets/{name}'] = value
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('Configuration exceeds transfer limits')
    files['manifest.json'] = json.dumps({'version': 1, 'sha256': {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}}, sort_keys=True).encode()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, value in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(value)
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(value))

def is_empty_state(destination):
    if not destination.exists():
        return True
    if not destination.is_dir() or destination.is_symlink():
        return False
    if not any(destination.iterdir()):
        return True
    if {p.name for p in destination.iterdir()} != {'servers.yaml', 'secrets'}:
        return False
    return ((destination / 'secrets').is_dir() and not any((destination / 'secrets').iterdir())
            and yaml.safe_load((destination / 'servers.yaml').read_text()) == yaml.safe_load(EMPTY_CONFIG))

def import_bundle(archive, destination, uid=None, gid=None):
    files = read_bundle(archive)  # Validate everything before changing destination.
    if not is_empty_state(destination):
        raise ValueError('Destination already contains configuration; export/backup it before replacing it')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.monitor-import-', dir=destination.parent))
    backup = None
    try:
        (staging / 'secrets').mkdir(mode=0o700)
        for name, value in files.items():
            path = staging / name
            path.write_bytes(value)
            path.chmod(0o600)
        if uid is not None:
            for path in [staging, *staging.rglob('*')]:
                os.chown(path, uid, gid)
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix='.monitor-empty-', dir=destination.parent))
            backup.rmdir()
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if backup:
                backup.rename(destination)
            raise
        if backup:
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

def init(destination, uid=None, gid=None):
    if destination.exists() and any(destination.iterdir()):
        # Imported configurations are preserved and checked, never replaced.
        config = yaml.safe_load((destination / 'servers.yaml').read_text())
        for name in validate_config(config):
            if not (destination / 'secrets' / name).is_file() or not (destination / 'secrets' / name).read_bytes().strip():
                raise ValueError(f'Missing referenced secret: {name}')
        return
    stream = io.BytesIO()
    with tempfile.TemporaryDirectory() as root:
        config = Path(root) / 'servers.yaml'
        config.write_bytes(EMPTY_CONFIG)
        export_bundle(config, Path(root), stream)
    stream.seek(0)
    import_bundle(stream, destination, uid, gid)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('--config', type=Path, default=Path(os.environ.get('MONITOR_CONFIG_PATH', 'servers.yaml')))
    exp.add_argument('--secrets', type=Path, default=Path(os.environ.get('MONITOR_SECRETS_PATH', '/run/secrets')))
    exp.add_argument('--output', default='-')
    imp = sub.add_parser('import')
    imp.add_argument('--archive', default='-')
    imp.add_argument('--destination', type=Path, default=Path('/config/state'))
    ini = sub.add_parser('init')
    ini.add_argument('--destination', type=Path, default=Path('/config/state'))
    for command in (imp, ini):
        command.add_argument('--uid', type=int)
        command.add_argument('--gid', type=int)
    preflight = sub.add_parser('can-import')
    preflight.add_argument('--archive', default='-')
    preflight.add_argument('--destination', type=Path, default=Path('/config/state'))
    check = sub.add_parser('verify')
    check.add_argument('--archive', default='-')
    args = parser.parse_args()
    try:
        if args.command == 'export':
            if args.output == '-':
                export_bundle(args.config, args.secrets, sys.stdout.buffer)
            else:
                # Exclusive creation prevents overwriting a previous backup.
                fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    with os.fdopen(fd, 'wb') as output:
                        export_bundle(args.config, args.secrets, output)
                except Exception:
                    Path(args.output).unlink()
                    raise
        elif args.command == 'init':
            init(args.destination, args.uid, args.gid)
        else:
            source = sys.stdin.buffer if args.archive == '-' else open(args.archive, 'rb')
            with (nullcontext(source) if source is sys.stdin.buffer else source):
                if args.command == 'import':
                    import_bundle(source, args.destination, args.uid, args.gid)
                else:
                    files = read_bundle(source)
                    if args.command == 'can-import' and not is_empty_state(args.destination):
                        raise ValueError('Destination already contains configuration')
                    print(f'Valid bundle: configuration and {len(files) - 1} referenced secrets')
    except (ValueError, OSError, KeyError, tarfile.TarError, json.JSONDecodeError, yaml.YAMLError) as error:
        parser.exit(2, f'Transfer failed: {error}\n')

if __name__ == '__main__':
    main()
