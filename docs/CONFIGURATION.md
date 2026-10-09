# Configuration Guide

## Server Configuration

The main configuration file is `servers.yaml` located in the project root. This file defines all servers to be monitored.

### Configuration Structure

```yaml
servers:
  database:
    <environment>:
      <hostname>:
        <database_name>:
          type: <database_type>
          port: <port_number>
          username: <username>
          password: <secret_name>
  application:
    <environment>:
      <server_name>:
        urls:
          - <url1>
          - <url2>
```

### Database Server Configuration

#### Supported Database Types

| Type | Database | Default Port |
|------|----------|--------------|
| `ora` | Oracle Database | 1521 |
| `pg` | PostgreSQL | 5432 |
| `mysql` | MySQL/MariaDB | 3306 |

#### Database Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Database type: `ora`, `pg`, or `mysql` |
| `port` | No | Connection port (uses default if omitted) |
| `username` | Yes | Database username |
| `password` | Yes | Secret name containing the password |

#### Example Database Configuration

```yaml
servers:
  database:
    production:
      db-server-01.example.com:
        app_database:
          type: ora
          port: 1521
          username: app_user
          password: db_password_prod
        analytics_db:
          type: pg
          port: 5432
          username: analytics
          password: analytics_password
    test:
      test-db.example.com:
        test_database:
          type: mysql
          username: tester
          password: db_password_test
```

### Application Server Configuration

#### Application Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `urls` | Yes | List of URLs to monitor |

#### Example Application Configuration

```yaml
servers:
  application:
    production:
      web-cluster:
        urls:
          - https://www.example.com
          - https://api.example.com/health
          - https://admin.example.com
    test:
      staging:
        urls:
          - https://staging.example.com
```

## Configuration and secrets in the suite

The suite mounts `dba-monitor-config` read-only at `/config` in the backend. The
configuration is `/config/state/servers.yaml`; referenced passwords are files under
`/config/state/secrets/`. Import a bundle using the suite's `monitor-import` command.
See [migration](MIGRATION.md) for export/import commands and verification.

Standalone Docker mounts the host `servers.yaml` at `/config/servers.yaml` and the
host `secrets/` directory at `/run/secrets`, both read-only. Secret file names may
be `SECRET_NAME` or `SECRET_NAME.txt`. Environment fallback uses the uppercased
secret name. Password values and secret references are excluded from API results.

## Runtime settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONITOR_CONFIG_PATH` | Legacy relative `servers.yaml` lookup | Backend configuration file |
| `MONITOR_SECRETS_PATH` | `/run/secrets` | Password files directory |
| `MONITOR_POLL_INTERVAL` | `60` | Backend polling interval in seconds |
| `MONITOR_API_URL` | `http://monitor-backend:8000` | Server-side frontend proxy destination |
| `MONITOR_HTTP_PORT` | `3103` | Suite browser port |
| `MONITOR_PROJECT_HOST` | `localhost` | Optional Traefik hostname |

The dashboard fetches `/api/status` every 30 seconds when auto refresh is enabled.
Browser API addresses no longer need build-time `NEXT_PUBLIC_*` settings. Configure
local development with `MONITOR_API_URL=http://127.0.0.1:8000`.

## Network checks

ICMP checks use a 2-second timeout, database connections a 5-second connection
timeout, and HTTP checks a 10-second timeout. HTTP health checks require status 200
and follow redirects. The current polling behavior skips database connections
when host ICMP fails. Ensure intranet DNS/routing and ICMP access from the new server.

Keep configuration archives and secret files out of Git. The suite binds browser
ports to loopback by default. Remote access requires private ingress or an
authenticated reverse proxy; Monitor itself has no UI login.
