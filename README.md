# Monitor

Monitor uses the shared DBA Tools theme and runs in Docker alongside Watchword,
Rollcall, and Muster. See [configuration transfer and deployment](docs/MIGRATION.md)
for moving an existing installation without direct access to its server.


A real-time infrastructure monitoring platform built with a modern full-stack architecture, providing unified visibility into database and application server health across multiple environments.

## Technology Stack

### Backend (Python/FastAPI)
- **FastAPI Framework** - High-performance async web framework with automatic OpenAPI documentation
- **Asynchronous Architecture** - Non-blocking event loop with `asyncio` for concurrent operations
- **Background Task Scheduling** - Automated polling with `asyncio.create_task()` for continuous monitoring
- **Thread Pool Execution** - `asyncio.to_thread()` for offloading synchronous database drivers
- **CORS Middleware** - Cross-Origin Resource Sharing configuration for frontend integration

### Frontend (Next.js/React)
- **Next.js 16** - React framework with App Router architecture
- **React 19** - Latest React with concurrent features and hooks-based state management
- **TypeScript** - Strongly-typed codebase with interface definitions for API contracts
- **Tailwind CSS 4** - Utility-first CSS framework for responsive, suite-themed UI
- **Client-Side Rendering** - `'use client'` directive with `useEffect` and `useState` hooks

### Database Connectivity
- **Oracle Database Driver** - `oracledb` thin mode
- **PostgreSQL Driver** - `psycopg2` with native binary support
- **MySQL Connector** - `mysql-connector-python` for MySQL/MariaDB support
- **Connection Pooling** - Per-check connection lifecycle with automatic cleanup
- **Timeout Handling** - Configurable connection timeouts (5 seconds default)

### Network Monitoring
- **ICMP Ping Implementation** - `ping3` library for host reachability verification
- **HTTP Health Checks** - `requests` library with redirect following and status validation
- **Timeout Management** - Network timeout handling (2s ping, 10s HTTP)

### Containerization (Docker)
- **Multi-Stage Builds** - Optimized frontend container with separate builder and runner stages
- **Docker Compose** - Service orchestration with dependency management
- **Docker Secrets** - Secure credential injection via `/run/secrets/` mount points
- **Volume Mounting** - External configuration file support

### Configuration Management
- **YAML Configuration** - Declarative server definitions with `pyyaml`
- **Environment Variables** - Server-side API routing and configurable backend polling
- **Secrets Fallback** - Docker secrets with environment variable fallback

## Monitoring Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-Database Support** | Oracle, PostgreSQL, MySQL connectivity verification |
| **Application Health** | HTTP/HTTPS endpoint monitoring with status code validation |
| **Network Verification** | ICMP ping for host reachability before service checks |
| **Environment Grouping** | Logical separation of production, test, development |
| **Real-Time Updates** | Configurable auto-refresh (default: 30 seconds) |
| **Status Caching** | In-memory cache for fast API responses |
| **Background Polling** | Continuous monitoring at 60-second intervals |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Returns current status of all monitored servers |
| `/health` | GET | Backend health check endpoint |

## Documentation

- [Installation Guide](docs/INSTALLATION.md) - Prerequisites and setup instructions
- [Configuration Guide](docs/CONFIGURATION.md) - Server configuration and environment variables
- [Architecture Overview](docs/ARCHITECTURE.md) - System design and component interaction

## Technical Specifications

See [specs/specs.txt](specs/specs.txt) for detailed technical specifications.

## License

See [LICENSE](LICENSE) for license information.

## MCP service status

Monitor provides read-only authenticated MCP tools at `/mcp` on its existing website port. Ask a connected assistant for service status, failures and environment summaries. See [MCP setup and tools](docs/MCP.md) for the private client token and deployment instructions.
