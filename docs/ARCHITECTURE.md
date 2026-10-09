# Architecture

An Nginx gateway serves the shared browser/MCP port, routing website traffic to the Next.js frontend and `/mcp` directly to the authenticated backend. Its `/api/status` handler
forwards status requests server-side to the FastAPI backend on the internal Docker
network, with caching disabled. Backend ports are not published to the host.

FastAPI validates configuration before startup, schedules a background poller, and
runs synchronous connection checks in a worker thread. It caches each completed
poll in memory. Oracle uses python-oracledb Thick mode; PostgreSQL and MySQL use their
respective drivers. Network checks use unprivileged ICMP sockets and HTTP requests.

The Docker suite uses one named volume for Monitor's YAML configuration and secret
files. The running backend mounts that volume read-only. A separate, offline
bootstrap/transfer container initializes or imports configuration with application
UID/GID ownership. Bundle transfer is an operator CLI workflow; credentials are
never exposed through the browser API.

See [configuration](CONFIGURATION.md) and [migration](MIGRATION.md) for runtime
settings, legacy export support, and deployment commands.

Oracle targets use canonical identities from the shared registry and SEPS wallets mounted read-only. Each login runs in an isolated Oracle Client process.

MCP tools use an atomically published status snapshot with freshness metadata. Its token has a dedicated persistent auth volume. Failed ICMP checks leave database checks unknown. MCP calls read cached observations without performing network checks.
