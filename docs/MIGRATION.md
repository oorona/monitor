# Move Monitor into the DBA suite

Monitor runs alongside Watchword, Rollcall, and Muster as the `monitor-backend` and
`monitor-frontend` services in the `dba-tools` Docker Compose project. Its default
browser URL is `http://localhost:3103`. The browser uses `/api/status` on that same
origin; the backend has no published host port.

Configuration and referenced password files live in the `dba-monitor-config` Docker
volume, under `state/servers.yaml` and `state/secrets/`. They survive image rebuilds,
updates, and container recreation. Monitor has no persistent results database: the
status cache is recreated by polling after startup. The shared PostgreSQL service
is not needed for Monitor's own state.

## Export from the old server

Direct access from the new deployment server is unnecessary. Copy
`scripts/monitor-config-export.py` to the intranet server. This is a standalone
utility and does not require updating, restarting, or stopping the old app.

For an existing Docker installation, find the backend container with `docker ps`.
Then run these commands from a private directory, replacing `OLD_BACKEND_CONTAINER`:

```bash
umask 077
set -o noclobber
docker exec -i OLD_BACKEND_CONTAINER python - export \
  --config /app/servers.yaml --secrets /run/secrets \
  < monitor-config-export.py > monitor-config.tar.gz
```

The exporter captures the active configuration file and every referenced secret
from the container's mounted files or its environment. Change `--config` and
`--secrets` if the old installation uses different paths. A failed export returns a
nonzero status; do not transfer an incomplete archive.

For an installation running directly on the host, use its Python environment
(which already has PyYAML) and its actual configuration and secrets directory:

```bash
python3 monitor-config-export.py export \
  --config /path/to/monitor/servers.yaml \
  --secrets /path/to/monitor/secrets \
  --output monitor-config.tar.gz
```

Host files named either `SECRET_NAME` or `SECRET_NAME.txt` are supported. If the
old app reads secrets from environment variables, invoke the exporter in that same
environment. The export fails if any referenced secret is unavailable.

The archive contains credentials in plaintext. Transfer it privately using your
approved method. Keep it outside Git and restrict access to the deploying account.
The bundle includes checksums to detect corruption; they are not a digital signature.

## Import on the shared deployment server

The new installation initially shows an empty dashboard. Copy the export onto this
server, then use an absolute archive path:

```bash
cd /home/iktdts/apps/website/watchword/deployment
./start.sh monitor-import /absolute/path/monitor-config.tar.gz
```

For the Git release installer:

```bash
./scripts/deploy-suite.sh monitor-import /path/to/runtime /absolute/path/monitor-config.tar.gz
```

Import checks the full bundle and destination before stopping Monitor, rejects
unsafe archive paths and missing secrets, preserves file bytes, and sets ownership
for the configured application UID/GID. Only Monitor is restarted. An existing
nonempty configuration is never overwritten. An empty first-install configuration
can be replaced by the imported one.

To export a configuration from the new suite for a backup or future move:

```bash
./start.sh monitor-export /absolute/path/monitor-backup.tar.gz
```

The export refuses an existing archive path. It does not stop the application.

## Verify before switching

1. Open Monitor and compare all environments, servers, database service names, and
   application URLs against the old instance.
2. Verify successful database and HTTP checks from the new server. Intranet DNS,
   routing, VPN access, firewall rules, and custom certificate trust are server
   prerequisites and are not carried by the configuration bundle. A hostname such
   as `localhost` or `host.docker.internal` now refers to the new location; review
   those references before switching.
3. Keep the old instance running until the new checks match, then change your
   browser-facing routing and stop the old instance on its server.

The API is a private operational dashboard, with the same loopback binding and
optional Traefik IP allowlist as the suite. Monitor does not add a new UI login.
Use the suite's private ingress or an authenticated reverse proxy for remote access.

Set `MONITOR_HTTP_PORT`, `MONITOR_PROJECT_HOST`, and, for Traefik,
`MONITOR_TRAEFIK_CERTRESOLVER` in the runtime `.env`. `MONITOR_SITE_URL` documents
the browser-facing origin; the frontend does not need it to contact its API.
`MONITOR_POLL_INTERVAL` controls backend polling in seconds; the dashboard refreshes
every 30 seconds and supports manual refresh, search, and environment filters.
