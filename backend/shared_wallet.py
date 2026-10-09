"""One Oracle wallet, selected once per connection; aliases identify secret entries."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ALIAS = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
GENERATION = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\Z")
BUNDLE_FILES = ("ewallet.p12", "cwallet.sso", "tnsnames.ora", "sqlnet.ora", "entries.json")


class SharedWalletError(ValueError):
    """Only fixed, secret-free messages cross the application boundary."""


def secret_key(alias):
    if not isinstance(alias, str) or not ALIAS.fullmatch(alias):
        raise SharedWalletError("Invalid shared wallet entry alias")
    return "watchword.password." + alias


def entries(directory):
    path = Path(directory) / "entries.json"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError()
        document = json.loads(path.read_text())
        if document.get("version") != 1 or not isinstance(document.get("entries"), dict):
            raise ValueError()
        for alias, item in document["entries"].items():
            secret_key(alias)
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]{0,127}", item.get("account", "")):
                raise ValueError()
            if set(item) != {"account", "privilege", "dbid", "db_unique_name", "container", "host", "port", "service"}:
                raise ValueError()
            if item["privilege"] not in {"normal", "sysdba", "sysoper", "sysbackup", "sysdg", "syskm"}:
                raise ValueError()
            if not isinstance(item["dbid"], str) or not re.fullmatch(r"[0-9]{1,20}", item["dbid"]):
                raise ValueError()
            for field in ("db_unique_name", "container", "service"):
                if not isinstance(item[field], str) or not re.fullmatch(r"[A-Za-z0-9_.$#-]{1,128}", item[field]):
                    raise ValueError()
            if not isinstance(item["host"], str) or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", item["host"]):
                raise ValueError()
            if type(item["port"]) is not int or not 1 <= item["port"] <= 65535:
                raise ValueError()
        return document["entries"]
    except (OSError, ValueError, TypeError, AttributeError):
        raise SharedWalletError("Shared wallet entry metadata is missing or invalid") from None


def check_bundle(directory):
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise SharedWalletError("Shared wallet generation is unavailable")
    for name in BUNDLE_FILES:
        path = directory / name
        try:
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) or mode & 0o077:
                raise ValueError()
        except (OSError, ValueError):
            raise SharedWalletError("Shared wallet bundle is incomplete or permissions are unsafe") from None
    return entries(directory)


def resolve_wallet(root, alias=None):
    root = Path(root)
    if not root.is_absolute() or any(p.is_symlink() for p in [root, *root.parents]):
        raise SharedWalletError("Shared wallet root must be an absolute mounted directory")
    pointer = root / "current"
    try:
        target = Path(os.readlink(pointer))
        if len(target.parts) != 2 or target.parts[0] != ".generations" or not GENERATION.fullmatch(target.parts[1]):
            raise ValueError()
        parent = root / ".generations"
        if parent.is_symlink():
            raise ValueError()
        directory = parent / target.parts[1]
        metadata = check_bundle(directory)
        if alias is not None:
            secret_key(alias)
            if alias not in metadata:
                raise SharedWalletError("Credential alias is not in the shared Oracle wallet")
        return directory
    except (OSError, ValueError) as error:
        if isinstance(error, SharedWalletError):
            raise
        raise SharedWalletError("Shared Oracle wallet is not initialized or its pointer is unsafe") from None


def read_credentials(directory, alias, client=Path("/opt/oracle/client")):
    key = secret_key(alias)
    metadata = check_bundle(directory)
    if alias not in metadata:
        raise SharedWalletError("Credential alias is not in the shared Oracle wallet")
    client = Path(client)
    try:
        result = subprocess.run(
            ["/usr/bin/java", "-cp", f"{client}/jlib/*:{client}/classes", "WalletSecret", str(directory), key],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, check=False,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
        )
        if result.returncode or not result.stdout or len(result.stdout) > 4096:
            raise ValueError()
        password = result.stdout.decode("utf-8")
        if any(c in password for c in "\r\n\x00"):
            raise ValueError()
        return metadata[alias]["account"], password
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise SharedWalletError("Shared Oracle wallet password entry is unavailable") from None
