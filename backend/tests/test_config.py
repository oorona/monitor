import pytest
from config import get_secret, validate_config


def test_secret_lookup_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv('MONITOR_SECRETS_PATH', str(tmp_path))
    assert get_secret('../password') is None


def test_named_and_legacy_txt_secret_files_and_environment_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv('MONITOR_SECRETS_PATH', str(tmp_path))
    monkeypatch.setenv('DATABASE_PASSWORD', 'environment-password')
    assert get_secret('database_password') == 'environment-password'
    (tmp_path / 'database_password.txt').write_text('file-password\n')
    assert get_secret('database_password') == 'file-password'
    (tmp_path / 'database_password').write_text('mounted-password\n')
    assert get_secret('database_password') == 'mounted-password'


def test_invalid_config_is_rejected():
    with pytest.raises(ValueError, match='servers mapping'):
        validate_config(None)
    with pytest.raises(ValueError, match='HTTP or HTTPS'):
        validate_config({'servers': {'application': {'prod': {'host': {'urls': ['file:///etc/passwd']}}}}})
