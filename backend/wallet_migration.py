"""Prepare an old Monitor export after provisioning its Oracle wallets.

The mapping JSON maps environment/hostname/service to a shared database UUID.
This command does not create accounts, change passwords, or alter the registry.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import yaml
from config import validate_config
from migration import read_bundle
from oracle_wallet import wallet_directory
from suite_registry import Document


def prepare(archive, registry_path, mapping, wallets_root, output):
    files = read_bundle(archive)
    config = yaml.safe_load(files['servers.yaml'])
    databases = {str(d.id): d for d in Document.model_validate_json(registry_path.read_text()).databases}
    old_keys = set()
    used_ids = set()
    for environment, servers in config['servers'].get('database', {}).items():
        for host, entries in list(servers.items()):
            for service, details in list(entries.items()):
                if details.get('type', 'ora') != 'ora':
                    continue
                key = f'{environment}/{host}/{service}'
                old_keys.add(key)
                database = databases.get(mapping.get(key))
                access = database.access.get('monitor') if database else None
                if not database or database.dialect != 'oracle' or not database.enabled or not access or not access.enabled or access.mode != 'wallet':
                    raise ValueError(f'Provision enabled Monitor wallet access for the mapped database: {key}')
                if (database.connect_kind != 'service' or (database.host or '').casefold() != host.casefold()
                        or (database.port or 1521) != details.get('port', 1521)
                        or (database.service_or_sid or '').casefold() != service.casefold()):
                    raise ValueError(f'Mapped Oracle endpoint does not match the legacy target: {key}')
                if str(database.id) in used_ids:
                    raise ValueError('Each legacy Oracle target must map to a distinct database ID')
                used_ids.add(str(database.id))
                wallet_directory(access.alias, wallets_root)
                del entries[service]
            if not entries:
                del servers[host]
    if set(mapping) != old_keys:
        raise ValueError('Mapping keys must match every legacy Oracle target exactly')
    required = validate_config(config)
    prepared = {'servers.yaml': yaml.safe_dump(config, sort_keys=False).encode()}
    prepared.update({f'secrets/{name}': files[f'secrets/{name}'] for name in required})
    prepared['manifest.json'] = json.dumps({'version': 1, 'sha256': {
        name: hashlib.sha256(value).hexdigest() for name, value in prepared.items()
    }}, sort_keys=True).encode()
    # Complete all validation before creating an output; never overwrite a backup.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as tar:
            for name, value in prepared.items():
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(value), 0o600
                tar.addfile(member, io.BytesIO(value))
    except BaseException:
        Path(output).unlink()
        raise
    return len(used_ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--mapping', required=True, type=Path)
    parser.add_argument('--wallets', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        with args.archive.open('rb') as archive:
            count = prepare(archive, args.registry, json.loads(args.mapping.read_text()), args.wallets, args.output)
    except (ValueError, OSError, KeyError, tarfile.TarError, yaml.YAMLError) as error:
        parser.exit(2, f'Wallet migration preparation failed: {error}\n')
    print(f'Prepared configuration: {count} Oracle targets use the shared registry; Oracle password files excluded.')


if __name__ == '__main__':
    main()
