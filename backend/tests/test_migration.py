import io
import json
import tarfile
from pathlib import Path
import pytest
from migration import export_bundle, import_bundle, init, read_bundle

CONFIG = b'''servers:
  database:
    production:
      db.internal:
        APPDB:
          type: pg
          username: monitor
          password: db_password_prod
  application:
    test:
      web.internal:
        urls: [https://web.internal/health]
'''

def bundle(tmp_path, monkeypatch=None):
    config = tmp_path / 'servers.yaml'
    config.write_bytes(CONFIG)
    secrets = tmp_path / 'secrets'
    secrets.mkdir(exist_ok=True)
    if monkeypatch:
        monkeypatch.setenv('DB_PASSWORD_PROD', 'env-password')
    else:
        (secrets / 'db_password_prod.txt').write_bytes(b'password-with-newline\n')
    output = io.BytesIO()
    export_bundle(config, secrets, output)
    output.seek(0)
    return output

def test_round_trip_preserves_config_and_secret_bytes_and_private_permissions(tmp_path):
    stream = bundle(tmp_path)
    destination = tmp_path / 'new/state'
    import_bundle(stream, destination)
    assert (destination / 'servers.yaml').read_bytes() == CONFIG
    assert (destination / 'secrets/db_password_prod').read_bytes() == b'password-with-newline\n'
    assert (destination / 'secrets/db_password_prod').stat().st_mode & 0o777 == 0o600
    init(destination)
    assert (destination / 'servers.yaml').read_bytes() == CONFIG

def test_environment_secrets_are_exported_from_running_process(tmp_path, monkeypatch):
    files = read_bundle(bundle(tmp_path, monkeypatch))
    assert files['secrets/db_password_prod'] == b'env-password'

def test_import_preserves_nonempty_destination(tmp_path):
    destination = tmp_path / 'state'
    destination.mkdir()
    (destination / 'keep').write_text('existing')
    with pytest.raises(ValueError, match='already contains'):
        import_bundle(bundle(tmp_path), destination)
    assert (destination / 'keep').read_text() == 'existing'

def test_empty_initial_configuration_can_be_replaced(tmp_path):
    destination = tmp_path / 'state'
    init(destination)
    import_bundle(bundle(tmp_path), destination)
    assert (destination / 'servers.yaml').read_bytes() == CONFIG

def test_missing_secret_refuses_export(tmp_path):
    config = tmp_path / 'servers.yaml'
    config.write_bytes(CONFIG)
    with pytest.raises(ValueError, match='Missing referenced secret'):
        export_bundle(config, tmp_path / 'absent', io.BytesIO())

def test_tampered_archive_is_rejected_before_changing_state(tmp_path):
    stream = bundle(tmp_path)
    files = {}
    with tarfile.open(fileobj=stream, mode='r:gz') as tar:
        for member in tar:
            files[member.name] = tar.extractfile(member).read()
    files['servers.yaml'] += b'changed: true\n'
    modified = io.BytesIO()
    with tarfile.open(fileobj=modified, mode='w:gz') as tar:
        for name, value in files.items():
            info = tarfile.TarInfo(name); info.size = len(value)
            tar.addfile(info, io.BytesIO(value))
    modified.seek(0)
    destination = tmp_path / 'new/state'
    with pytest.raises(ValueError, match='checksum'):
        import_bundle(modified, destination)
    assert not destination.exists()

@pytest.mark.parametrize('name', ['../escape', '/etc/passwd', 'secrets/../../escape'])
def test_archive_traversal_is_rejected(name):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        member = tarfile.TarInfo(name); member.size = 1
        tar.addfile(member, io.BytesIO(b'x'))
    stream.seek(0)
    with pytest.raises(ValueError, match='Unsafe'):
        read_bundle(stream)
