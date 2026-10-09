# Configuration

Oracle targets come exclusively from the suite's shared databases.json. Enable
Monitor access in the shared Database Registry and enter an existing shared wallet credential
alias. The registry supplies the canonical name, stable database UUID, environment
and host. Display-name changes do not rename a wallet credential. Monitor uses
Thick-mode connections in an isolated worker. The worker reads the selected named password entry from the one shared Oracle wallet and uses transient credentials. SYS/SYSTEM and administrative entries are rejected for Monitor workloads.

Mount the registry at `/registry` and the exact same `WALLET_HOST_PATH` root used by all four apps at `/wallets`, both read-only. `/wallets/current` selects a complete shared wallet snapshot with `cwallet.sso`, `ewallet.p12`, `entries.json`, `tnsnames.ora` and `sqlnet.ora`. Every credential alias is an entry in that wallet; it is not a separate directory. There is no Monitor wallet namespace or separate host path override.

servers.yaml contains PostgreSQL, MySQL and application URL checks:

```yaml
servers:
  database:
    production:
      pg.internal:
        appdb:
          type: pg
          username: monitor
          password: pg_password
  application:
    production:
      web:
        urls: [https://web.internal/health]
```

Non-Oracle passwords reference private NAME or NAME.txt files. Legacy environment
fallback uses the uppercased name. PostgreSQL/MySQL default ports are 5432/3306.
Oracle targets must be registered in the shared database registry; Oracle passwords are not accepted in YAML.

| Variable | Purpose |
|----------|---------|
| SUITE_REGISTRY_ROOT | Shared registry directory; suite uses /registry |
| ORACLE_WALLET_ROOT | The one shared wallet root; default /wallets |
| ORACLE_CLIENT_LIB_DIR | Client libraries; Docker uses /opt/oracle/client/lib |
| MONITOR_CONFIG_PATH | YAML path; suite uses /config/state/servers.yaml |
| MONITOR_SECRETS_PATH | Non-Oracle secrets; suite uses /config/state/secrets |
| MONITOR_POLL_INTERVAL | Backend polling seconds; default 60 |
| MONITOR_API_URL | Frontend server proxy; suite uses http://monitor-backend:8000 |
| MONITOR_HTTP_PORT | Suite loopback browser port; default 3103 |

ICMP checks use 2 seconds, Oracle workers at most 8 seconds, PostgreSQL/MySQL
connections 5 seconds, and HTTP checks 10 seconds. Host ICMP failure skips database
checks. DSN-only Oracle entries without a host skip ICMP and use their wallet.
The dashboard supports environment filtering, search, manual refresh and a
30-second automatic refresh.

MCP uses MONITOR_MCP_TOKEN_FILE (default /run/monitor-auth/token), MONITOR_PROJECT_HOST for allowed Host headers, and MONITOR_SITE_URL for the allowed browser origin. See [MCP](MCP.md).
