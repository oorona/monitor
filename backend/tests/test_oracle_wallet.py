import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from config import validate_config
from migration import export_bundle, import_bundle, read_bundle
from oracle_wallet import check_oracle, load_oracle_targets, wallet_directory, BUNDLE_FILES
from suite_registry import Access, DatabaseInput, Registry
from wallet_migration import prepare


def target(tmp_path):
    registry = tmp_path / 'registry'
    registry.mkdir()
    entry = Registry(registry).save(DatabaseInput(name='canonical-prod', host='db.internal', service_or_sid='APPDB', environment='prod', access={'monitor': Access(alias='existing-reader')}), 'watchword')
    wallets = tmp_path / 'wallets'
    wallet = wallets / '.generations/existing-reader/generation'
    wallet.mkdir(parents=True)
    for name in BUNDLE_FILES:
        (wallet / name).write_bytes(b'test-only')
    (wallets / 'existing-reader').symlink_to('.generations/existing-reader/generation')
    return registry, entry, wallets, wallet


def test_registry_supplies_canonical_id_name_and_exact_alias(tmp_path, monkeypatch):
    registry, entry, wallets, wallet = target(tmp_path)
    monkeypatch.setenv('SUITE_REGISTRY_ROOT', str(registry))
    assert load_oracle_targets() == [entry]
    assert wallet_directory('existing-reader', wallets) == wallet
    Registry(registry).save(DatabaseInput(**entry.model_dump(exclude={'id','revision','updated_by'})).model_copy(update={'enabled': False}), 'watchword', entry.id, 1)
    assert load_oracle_targets() == []


def test_no_oracle_password_config_can_reach_the_poller():
    legacy = {'servers': {'database': {'prod': {'db': {'service': {'type':'ora','username':'reader','password':'pw'}}}}}}
    with pytest.raises(ValueError, match='shared registry'):
        validate_config(legacy)
    assert validate_config(legacy, allow_legacy_oracle=True) == {'pw'}


def test_unsafe_wallet_alias_symlinks_and_missing_files(tmp_path):
    registry, entry, wallets, wallet = target(tmp_path)
    with pytest.raises(ValueError):
        wallet_directory('../existing-reader', wallets)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (wallets / 'escape').symlink_to(outside)
    with pytest.raises(ValueError, match='escapes'):
        wallet_directory('escape', wallets)
    (wallet / 'sqlnet.ora').unlink()
    with pytest.raises(ValueError, match='incomplete'):
        wallet_directory('existing-reader', wallets)


def test_login_process_is_bounded_and_contains_no_credentials(tmp_path, monkeypatch):
    registry, entry, wallets, wallet = target(tmp_path)
    monkeypatch.setenv('ORACLE_WALLET_ROOT', str(wallets))
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"ok":true}'))
    monkeypatch.setattr('oracle_wallet.subprocess.run', run)
    assert check_oracle('existing-reader') == (True, None)
    request = json.loads(run.call_args.kwargs['input'])
    assert request['alias'] == 'existing-reader'
    assert not set(request) & {'user','username','password','wallet_password'}
    assert run.call_args.kwargs['timeout'] == 8


def test_worker_uses_external_auth_and_rejects_admin_wallet(monkeypatch):
    import oracle_wallet_worker as worker
    conn = Mock()
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    conn.cursor.return_value = cursor
    connect = Mock(return_value=conn)
    monkeypatch.setattr(worker.oracledb, 'init_oracle_client', Mock())
    monkeypatch.setattr(worker.oracledb, 'connect', connect)
    cursor.fetchone.side_effect = [('MONITOR_RO','MONITOR_RO'), (1,)]
    assert worker.check({'wallet_dir':'/wallets/existing-reader','alias':'existing-reader'}) == {'ok':True}
    connect.assert_called_once_with(dsn='existing-reader', externalauth=True)
    cursor.fetchone.side_effect = [('SYS','SYS')]
    with pytest.raises(ValueError, match='Administrative'):
        worker.check({'wallet_dir':'/wallets/existing-reader','alias':'existing-reader'})


def test_legacy_bundle_requires_mapping_and_strips_oracle_secrets(tmp_path):
    registry, entry, wallets, wallet = target(tmp_path)
    config = tmp_path / 'servers.yaml'
    config.write_text('servers:\n  database:\n    prod:\n      db.internal:\n        APPDB:\n          type: ora\n          username: reader\n          password: old_oracle\n  application: {}\n')
    secrets = tmp_path / 'secrets'
    secrets.mkdir()
    (secrets / 'old_oracle').write_text('legacy-value-must-not-be-imported')
    stream = io.BytesIO()
    export_bundle(config, secrets, stream)
    stream.seek(0)
    with pytest.raises(ValueError, match='prepare the legacy bundle'):
        import_bundle(stream, tmp_path/'state')
    assert not (tmp_path/'state').exists()
    stream.seek(0)
    output = tmp_path/'prepared.tar.gz'
    mapping = {'prod/db.internal/APPDB': str(entry.id)}
    assert prepare(stream, registry/'databases.json', mapping, wallets, output) == 1
    with output.open('rb') as archive:
        files = read_bundle(archive)
    assert set(files) == {'servers.yaml'}
    assert b'legacy-value' not in files['servers.yaml']
    with output.open('rb') as archive:
        import_bundle(archive, tmp_path/'state')
    assert not any((tmp_path/'state/secrets').iterdir())


def test_mapping_cannot_silently_redirect_a_legacy_database(tmp_path):
    registry, entry, wallets, wallet = target(tmp_path)
    config=tmp_path/'servers.yaml'
    config.write_text('servers: {database: {prod: {wrong-host: {APPDB: {type: ora, username: reader, password: old}}}}}')
    secrets=tmp_path/'secrets';secrets.mkdir();(secrets/'old').write_text('private')
    stream=io.BytesIO();export_bundle(config,secrets,stream);stream.seek(0)
    output=tmp_path/'prepared.tar.gz'
    with pytest.raises(ValueError,match='endpoint'):
        prepare(stream,registry/'databases.json',{'prod/wrong-host/APPDB':str(entry.id)},wallets,output)
    assert not output.exists()
