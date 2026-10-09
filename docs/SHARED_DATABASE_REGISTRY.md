# Shared database registry

Watchword, Rollcall and Muster use the same v1 database registry. Their application
PostgreSQL databases, secrets, histories, policies and deployments remain independent.
The registry contains database metadata and application access references, never passwords.
The schema is [database-registry.schema.json](database-registry.schema.json).

## Docker configuration

The combined suite reads the one `.env` in the Watchword checkout. Set `DATABASE_REGISTRY_HOST_PATH` and `WALLET_HOST_PATH` there. All applications use the same absolute host directories with matching APP_UID/APP_GID.

The registry is mounted at `/registry`; directory-level mounting permits atomic document replacement. Every Oracle consumer mounts the same wallet root read-only at `/wallets`, while Watchword's executor writes it. The registry selects credential entries by alias; it does not create passwords or wallets. Independent deployments must use exactly the same host paths in their configuration. The base Compose files provide the wallet mount without a provisioning overlay.

Run Watchword's existing bootstrap (`watchword-init secrets`, or `suite-init secrets`
in a newly assembled suite) before starting the applications. It initializes directory
ownership and preserves and validates an existing registry. For independently installed
Rollcall/Muster instances, initialize the directory on the Docker host first:

```sh
sudo install -d -m 0700 -o 1000 -g 1000 /srv/dba-tools/databases
```

Use the actual matching UID/GID for all application containers. Keep the directory private
and on the same Docker host's local filesystem, which must support POSIX `flock`,
atomic rename and `fsync`. Separate Docker Compose projects share this bind mount;
a named volume private to one project would not supply a common inventory.
Back up the whole registry directory together with application metadata and wallets.
A corrupt or unsupported registry blocks shared writes and target resolution; it is
never silently overwritten or replaced by an empty list.

## Adding and changing databases

Use **Suite databases** in Rollcall/Muster or the **Databases** tab in Watchword.
All three screens use the same schema and writer. A database has a stable UUID,
unique name (case insensitive), dialect, connection metadata, environment, timezone,
tags and enabled flag. Oracle wallet aliases are entered separately for each app.
For example, one PDB can have `rollcall-prod` and `muster-prod` access using different
read-only accounts. A credential alias is globally unique in the shared wallet.
Every consumer resolves `/wallets/current` once and reads its selected alias from that same wallet. The same alias can be shared across applications for the same database.

Rollcall/Muster project registry entries into local targets. Entries without enabled
access are visible but cannot run. Tags and connection metadata are shared; variables,
blackout windows, concurrency limits, health, schedules and results stay local.
SQLite paths are relative to each application's own data directory; a shared SQLite
entry does not share a file. Non-Oracle credentials are configured separately in each
application's database settings and remain encrypted there.

Existing target create/import APIs and CLI imports publish through the same registry
writer when `SUITE_REGISTRY_ROOT` is configured. Existing target updates include
`registry_revision` from the target response. Use the shared screen to change an
Oracle endpoint; app database settings edit its wallet access and local run settings.

Watchword can link credential inventory records to `database_id`. Database inventory
and account inventory have different lifecycles: adding a database does not register
an account for rotation or establish its DBID/container identity. Expected identity,
account scope and discovery evidence remain explicitly managed in Watchword.

To retire access, disable that app's access in the shared screen. Clearing an existing
binding retains it disabled so its history ID remains addressable. Disable the database
globally to stop all consumer access. Shared targets cannot be hard-deleted through the
local target API; historical references and wallet files are preserved.

## Writer rules for every application

1. Validate against the strict v1 schema. Unknown fields, invalid tags/timezones,
   duplicate names/aliases and credential-bearing DSNs are rejected.
2. Acquire `.registry.lock` with an exclusive POSIX lock before reading or changing
   the document. The lock file is never renamed or deleted.
3. Update by database UUID and expected `revision`; reject stale revisions with 409.
   Preserve other applications' access and stable target IDs.
4. Write a private temporary file in the same directory, flush and `fsync`, atomically
   replace `databases.json`, then `fsync` the directory. Each update increments revision.
5. Read the registry again before target selection and before a fresh connection.
   Background synchronization runs every five seconds when background tasks are enabled.
   Already running queries complete using their existing connection.

The authenticated API is `/suite/databases` on Watchword's backend and
`/api/suite/databases` on Rollcall/Muster. `GET` returns the versioned document,
`POST` adds a record, and `PUT /<uuid>` updates with an expected revision.
Rollcall/Muster also expose `POST /adopt-local`. Existing app authentication,
CSRF protection and write limits apply; there is no public registry endpoint.

## Keeping the suite consistent

`backend/app/suite_registry.py`, `frontend/app/suite-theme.css` and
`frontend/components/DatabaseRegistry.tsx` are the common contract, kept identical
in the three writer repositories. Monitor carries the same backend registry contract.
Update all four registry contracts together when changing them.
The checked-in JSON schema and this document must also stay identical. Run
Watchword's `scripts/check-suite-contract.py --source-root /home/iktdts/apps/website`
to detect drift. Do not edit live JSON or introduce another private inventory format.

The common CSS follows Watchword's forest-green light palette and warm paper surfaces,
with neutral charcoal surfaces and warm accents in dark mode. Both themes share
serif page headings and restrained controls. `prefers-color-scheme` follows the OS
in both light and dark mode, including native form controls, without a stored override.

## Monitor and required Oracle authentication

Monitor reads the registry read-only and selects its globally unique credential alias from the same shared wallet as the other apps. Its status uses the canonical database UUID, name and environment. No display label is converted into an account alias.

All Oracle application bindings require shared wallet mode. SYS/SYSTEM or administrative entries cannot be used by consumers; choose an ordinary account with workload-appropriate grants. PostgreSQL and SQLite local settings remain supported. There is no separate Monitor wallet directory or override.
