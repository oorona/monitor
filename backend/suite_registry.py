"""DBA suite registry v1. Keep this contract identical in all four repositories."""
import fcntl
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

APPS = ("watchword", "rollcall", "muster", "monitor")


class RegistryError(Exception):
    pass


class RegistryConflict(RegistryError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Access(Strict):
    target_id: UUID | None = None
    mode: Literal["wallet", "local"] = "wallet"
    alias: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    username: str | None = Field(default=None, max_length=128)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_access(self):
        if self.mode == "wallet" and (not self.alias or self.username):
            raise ValueError("Wallet access needs an alias and no username")
        if self.mode == "local" and self.alias:
            raise ValueError("Local access cannot contain a wallet alias")
        if (self.username or "").strip().strip('"').upper() in {"SYS", "SYSTEM"}:
            raise ValueError("Administrative accounts belong in Watchword credential inventory")
        return self


class DatabaseInput(Strict):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
    dialect: Literal["oracle", "postgres", "sqlite"] = "oracle"
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    connect_kind: Literal["service", "sid", "dsn"] = "service"
    service_or_sid: str | None = Field(default=None, max_length=255)
    dsn: str | None = Field(default=None, max_length=2000)
    container: str | None = Field(default=None, max_length=128)
    environment: str = Field(default="unknown", min_length=1, max_length=64)
    timezone: str = Field(default="UTC", max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=30)
    enabled: bool = True
    access: dict[Literal["watchword", "rollcall", "muster", "monitor"], Access] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (KeyError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, values):
        tags = sorted(set(v.strip().lower() for v in values))
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,49}", v) for v in tags):
            raise ValueError("Invalid tag")
        return tags

    @model_validator(mode="after")
    def connection(self):
        # DSNs are metadata, never a credential transport.
        if self.dsn and (re.search(r"(?i)(password|passwd|pwd)\s*[=:]", self.dsn) or
                         re.search(r"://[^/]*@", self.dsn) or
                         re.search(r"^[^/\s]+/[^@\s]+@", self.dsn)):
            raise ValueError("Credentials are forbidden in registry DSNs")
        if self.dialect == "sqlite":
            if not self.dsn or self.dsn.startswith("/") or ".." in self.dsn.split("/"):
                raise ValueError("SQLite needs a path relative to each application's data directory")
            self.connect_kind = "dsn"
        elif self.connect_kind == "dsn":
            if not self.dsn:
                raise ValueError("DSN is required")
        elif not self.host or not self.service_or_sid:
            raise ValueError("Host and service/SID are required")
        if self.dialect != "oracle" and any(a.mode == "wallet" for a in self.access.values()):
            raise ValueError("Wallet access requires Oracle")
        return self


class Database(DatabaseInput):
    id: UUID
    revision: int = Field(ge=1)
    updated_by: Literal["watchword", "rollcall", "muster", "monitor"]


class DatabaseUpdate(DatabaseInput):
    revision: int = Field(ge=1)


class Document(Strict):
    schema_version: Literal[1] = 1
    databases: list[Database] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def unique(self):
        if len({d.id for d in self.databases}) != len(self.databases) or len({d.name.casefold() for d in self.databases}) != len(self.databases):
            raise ValueError("Database IDs and names must be unique")
        for app in APPS:
            ids = [d.access[app].target_id for d in self.databases if app in d.access and d.access[app].target_id]
            if len(set(ids)) != len(ids):
                raise ValueError("Application target IDs must be unique")
            aliases = [d.access[app].alias for d in self.databases if app in d.access and d.access[app].alias]
            if len(set(aliases)) != len(aliases):
                raise ValueError("A wallet alias may belong to only one database per app")
        return self


def registry_root():
    value = os.environ.get("SUITE_REGISTRY_ROOT")
    return Path(value) if value else None


class Registry:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "databases.json"

    @contextmanager
    def _lock(self, write=False):
        if not self.root.is_dir() or self.root.is_symlink():
            raise RegistryError("Mount a private, writable SUITE_REGISTRY_ROOT directory")
        try:
            fd = os.open(self.root / ".registry.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
                yield
        except OSError as exc:
            raise RegistryError("Shared database registry is unavailable or not writable") from exc

    def _read(self):
        if self.path.is_symlink():
            raise RegistryError("Registry must be a regular file")
        try:
            if not self.path.exists():
                return Document()
            if self.path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("Too large")
            return Document.model_validate_json(self.path.read_text())
        except (ValueError, OSError) as exc:
            raise RegistryError("Invalid database registry; restore a valid v1 file before continuing") from exc

    def read(self):
        with self._lock():
            return self._read()

    def create_with_id(self, body, app, database_id):
        return self.save(body, app, new_id=database_id)

    def save(self, body: DatabaseInput, app: str, database_id=None, revision=None, new_id=None):
        if body.dialect == "oracle" and any(a.mode != "wallet" for a in body.access.values()):
            raise RegistryConflict("Oracle application access requires an external password-store wallet")
        with self._lock(True):
            document = self._read()
            existing = next((d for d in document.databases if d.id == database_id), None)
            if database_id is not None and (existing is None or existing.revision != revision):
                raise RegistryConflict("Database changed; reload the registry before saving")
            if new_id and any(d.id == new_id for d in document.databases):
                raise RegistryConflict("Database ID already registered")
            if existing and existing.dialect != body.dialect:
                raise RegistryConflict("Database type cannot change; register a separate database")
            data = body.model_dump(exclude={"revision"})
            if existing:
                for tool, previous in existing.access.items():
                    if tool not in data["access"]:
                        # Omission is not permission to revoke another application's access.
                        data["access"][tool] = previous.model_dump()
                    elif previous.target_id:
                        requested_id = data["access"][tool].get("target_id")
                        if requested_id and requested_id != previous.target_id:
                            raise RegistryConflict("Application target IDs cannot be reassigned")
                        data["access"][tool]["target_id"] = previous.target_id
            if body.dialect == "oracle" and any(a["mode"] != "wallet" for a in data["access"].values()):
                raise RegistryConflict("Oracle application access requires an external password-store wallet")
            value = Database(**data, id=existing.id if existing else (new_id or uuid4()),
                             revision=existing.revision + 1 if existing else 1, updated_by=app)
            entries = [d for d in document.databases if d.id != value.id] + [value]
            try:
                document = Document(databases=sorted(entries, key=lambda d: d.name.casefold()))
            except ValueError as exc:
                raise RegistryConflict("Database name or wallet alias already registered") from exc
            temp = None
            try:
                fd, temp = tempfile.mkstemp(prefix=".databases-", dir=self.root)
                with os.fdopen(fd, "w") as handle:
                    handle.write(document.model_dump_json(indent=2) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, self.path)
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if temp and os.path.exists(temp):
                    os.unlink(temp)
            return value
