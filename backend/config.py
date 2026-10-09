"""Configuration shared by the poller and portable configuration bundles."""
import os
import re
from pathlib import Path
import yaml

SECRET_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")

def validate_config(config, *, allow_legacy_oracle=False):
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
                        if details.get('type', 'ora') == 'ora' and not allow_legacy_oracle:
                            raise ValueError('Oracle targets must be configured in the shared registry with Monitor wallet access; prepare the legacy bundle before importing')
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
