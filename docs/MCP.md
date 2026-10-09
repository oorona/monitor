# Ask questions about Monitor status through MCP

Monitor exposes authenticated Streamable HTTP MCP at the same address as its
website: `http://SERVER:3103/mcp` in the suite, or `http://SERVER:4000/mcp` standalone.
Its Nginx gateway routes `/mcp` directly to the backend and website requests to
Next.js. Traefik is unnecessary. The MCP server runs inside the existing backend;
the gateway is Monitor's third continuously running container.

A connected AI assistant can answer questions such as:

- Which production services need attention?
- Is the finance database reachable?
- Which HTTP checks are failing?
- What is the latest observed status of this service?

## Tools

| Tool | Purpose |
|------|---------|
| `get_monitor_summary` | Health counts by kind and environment, with observation time |
| `list_services` | Search by host, service name or database UUID; filter by environment, kind and state |
| `list_problems` | Failed or unknown checks, with pagination |
| `get_service_status` | One exact service ID returned by `list_services` |

Every result includes the last successful poll time, data age, stale threshold and
whether the latest poll failed. Until the first poll finishes, data is initializing.
A failed poll or data older than twice the polling interval (at least 120 seconds)
is stale. Tools return cached observations and never start extra network checks.
Host, database and HTTP checks are counted separately. A failed ICMP check makes
skipped database connections unknown; it does not establish a database outage.
An empty inventory is not evidence that all services are healthy. No history or
outage duration is available in this version.

Only status fields are returned. Password references, usernames, wallet locations,
URL user information, query strings, fragments and raw driver diagnostics are
excluded. Tools cannot modify configuration, run SQL, restart services or rotate
credentials. Oracle target credentials continue to live exclusively in the one shared Oracle wallet.

## Authentication and setup

MCP requires `Authorization: Bearer TOKEN`. This token authenticates the MCP client;
it is separate from Oracle credentials. Missing or incorrect tokens are rejected.
The suite stores it in the private `dba-monitor-auth` Docker volume, mounted
read-only into the backend at `/run/monitor-auth/token`. Bootstrap generates it once
and preserves it during updates; it is never printed during initialization.

For a fresh suite installation, the installer initializes this volume automatically.
For an already assembled release, initialize it before starting the updated services:

```bash
docker compose -f compose.yaml --profile bootstrap run --rm monitor-mcp-init
docker compose -f compose.yaml up -d --wait monitor-backend monitor-frontend monitor-gateway
```

The normal Git installer update also runs this bootstrap. Configure
`MONITOR_PROJECT_HOST` to the private IP or hostname MCP clients use, and
`MONITOR_SITE_URL` to the corresponding browser origin. The backend checks Host
and Origin headers. Set `HTTP_BIND` to the server's private IP for intranet access;
the default remains loopback. Carry bearer tokens over trusted TLS ingress or an
SSH tunnel; the direct gateway does not terminate TLS.

To retrieve the token privately for your MCP client's settings, run on the server:

```bash
docker compose -f compose.yaml exec -T monitor-backend cat /run/monitor-auth/token
```

Configure the client's remote MCP URL and bearer authorization header. A common
configuration format is:

```json
{
  "mcpServers": {
    "monitor": {
      "url": "http://SERVER:3103/mcp",
      "headers": {"Authorization": "Bearer YOUR_PRIVATE_MONITOR_TOKEN"}
    }
  }
}
```

The exact settings format depends on the client. Do not commit a populated client
configuration or token. Clients must support remote HTTP MCP with bearer tokens.

For standalone Docker:

```bash
docker compose --profile bootstrap run --rm --build mcp-init
docker compose up -d --build
```

Standalone custody is `mcp-auth/token`, ignored by Git and excluded from suite
assemblies. To revoke a token, stop Monitor, replace that private file with a new
`monitor_` token generated using `secrets.token_urlsafe(32)`, preserve its ownership
and mode 0600, then restart. Tokens are read on every request, so changing the
file invalidates the old token. There is one shared read-only client token in this
version; per-client keys and scopes are not implemented.

Monitor configuration exports do not include MCP tokens. A new server generates
a new token, which you then install in the clients. Do not modify the old instance
until migration and real wallet logins are verified.

## Protocol references

The implementation uses [FastMCP HTTP integration](https://gofastmcp.com/deployment/http)
and [token verification](https://gofastmcp.com/servers/auth/token-verification),
aligned with the existing Rollcall and Muster MCP servers.
