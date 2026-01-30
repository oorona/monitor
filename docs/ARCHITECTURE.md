# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Client                                  │
│                         (Web Browser)                                │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTP (port 4000)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend Container                           │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Next.js 16 / React 19                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   page.tsx  │  │  types.ts   │  │   Tailwind CSS 4    │   │  │
│  │  │  (Dashboard)│  │ (Interfaces)│  │   (Dark Theme UI)   │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ HTTP API (port 9000)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Backend Container                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    FastAPI / Uvicorn ASGI                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │   main.py   │  │ monitor.py  │  │     config.py       │   │  │
│  │  │ (API Routes)│  │  (Polling)  │  │  (YAML + Secrets)   │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────┬─────────────────┬─────────────────┬─────────────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │    Oracle     │ │  PostgreSQL   │ │     MySQL     │
    │   Databases   │ │   Databases   │ │   Databases   │
    └───────────────┘ └───────────────┘ └───────────────┘
            │                 │                 │
            └─────────────────┴─────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Application     │
                    │     Servers       │
                    │  (HTTP Endpoints) │
                    └───────────────────┘
```

## Project Structure

```
monitor/
├── backend/
│   ├── main.py              # FastAPI application and routes
│   ├── monitor.py           # Server monitoring logic
│   ├── config.py            # Configuration and secrets loading
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Backend container definition
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Main dashboard component
│   │   ├── types.ts         # TypeScript interfaces
│   │   ├── layout.tsx       # Root layout
│   │   └── globals.css      # Global styles
│   ├── package.json         # Node.js dependencies
│   └── Dockerfile           # Frontend container definition
├── docs/
│   ├── INSTALLATION.md      # Installation instructions
│   ├── CONFIGURATION.md     # Configuration guide
│   └── ARCHITECTURE.md      # This file
├── specs/
│   └── specs.txt            # Technical specifications
├── secrets/                 # Docker secrets (gitignored)
├── docker-compose.yml       # Container orchestration
├── servers.yaml             # Server configuration (gitignored)
├── servers.yaml.example     # Configuration template
└── README.md                # Project overview
```

## Component Details

### Backend Components

#### main.py - API Server
- Initializes FastAPI application
- Configures CORS middleware
- Defines API endpoints (`/status`, `/health`)
- Starts background polling task on startup

#### monitor.py - Monitoring Engine
- `poll_servers()` - Main polling function that iterates through all configured servers
- `check_ping()` - ICMP ping verification using ping3
- `check_oracle()` - Oracle database connection test using oracledb
- `check_postgres()` - PostgreSQL connection test using psycopg2
- `check_mysql()` - MySQL connection test using mysql-connector
- `check_url()` - HTTP endpoint health check using requests
- `get_status()` - Returns cached status data

#### config.py - Configuration Loader
- `load_config()` - Parses servers.yaml configuration
- `get_secret()` - Retrieves secrets from Docker secrets or environment

### Frontend Components

#### page.tsx - Dashboard
- Main React component with status display
- Uses `useEffect` for data fetching and auto-refresh
- Uses `useState` for status, loading, error, and refresh toggle
- Renders environment-grouped server cards

#### types.ts - Type Definitions
- `StatusResponse` - Root API response structure
- `ServerDatabaseStatus` - Database server status
- `ApplicationStatus` - Application server status
- `DatabaseDetails` - Database connection details

## Data Flow

### Polling Cycle

1. **Startup**: `main.py` starts background poller via `asyncio.create_task()`
2. **Load Config**: `monitor.py` loads `servers.yaml` via `config.py`
3. **Iterate Servers**: For each server in configuration:
   - Ping host to verify network connectivity
   - If reachable, test database connections or HTTP endpoints
4. **Cache Results**: Store results in `server_status_cache` dictionary
5. **Sleep**: Wait 60 seconds before next poll cycle

### API Request Flow

1. **Frontend Request**: React `useEffect` fetches `/status` endpoint
2. **Backend Response**: FastAPI returns cached `server_status_cache`
3. **State Update**: React updates component state with response
4. **Render**: Dashboard renders status cards for each server

## Status Data Structure

```json
{
  "database": {
    "<environment>": {
      "<hostname>": {
        "ping": true,
        "ping_error": null,
        "databases": {
          "<db_name>": {
            "status": true,
            "error": null,
            "details": {
              "port": 5432,
              "username": "user",
              "password": "secret_name"
            }
          }
        }
      }
    }
  },
  "application": {
    "<environment>": {
      "<server_name>": {
        "ping": true,
        "ping_error": null,
        "urls": {
          "<url>": {
            "status": true,
            "error": null
          }
        },
        "details": {
          "urls": ["<url>"]
        }
      }
    }
  }
}
```

## Container Architecture

### Backend Container

```dockerfile
FROM python:3.11-slim-bullseye

# Includes Oracle Instant Client 21.12 for Oracle connectivity
# Exposes port 8000 for Uvicorn ASGI server
# Mounts servers.yaml and Docker secrets at runtime
```

### Frontend Container

```dockerfile
# Stage 1: Builder
FROM node:20-alpine AS builder
# Installs dependencies and builds Next.js application

# Stage 2: Runner
FROM node:20-alpine AS runner
# Copies standalone build output
# Exposes port 3000 for Next.js server
```

## Networking

### Docker Compose Network

- Backend and frontend share default Docker network
- Frontend accesses backend via `backend:8000` internally
- Frontend exposed on host port 4000
- Backend exposed on host port 9000

### External Connectivity

- Backend requires network access to monitored servers
- ICMP ping requires appropriate permissions
- Database ports must be accessible (1521, 5432, 3306)
- HTTP/HTTPS endpoints must be reachable

## Error Handling

### Backend Error Handling
- Each check function returns `(success: bool, error: str|None)`
- Failed checks include error messages in response
- Polling continues even if individual checks fail
- All exceptions are caught and logged

### Frontend Error Handling
- API fetch failures display error banner
- Individual server errors shown in status cards
- Auto-refresh continues despite errors
- Loading state shown during initial fetch
