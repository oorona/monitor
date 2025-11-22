import yaml
import os
from typing import Dict, Any

def get_secret(secret_name: str, default: str = None) -> str:
    """Reads a secret from Docker secrets or environment variables."""
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.environ.get(secret_name.upper(), default)

def load_config(config_path: str = "../servers.yaml") -> Dict[str, Any]:
    """Loads the server configuration from YAML."""
    if not os.path.exists(config_path):
        # Fallback for running from backend dir
        config_path = "servers.yaml"
        if not os.path.exists(config_path):
             # Fallback for running from project root
            config_path = "servers.yaml"
            
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

