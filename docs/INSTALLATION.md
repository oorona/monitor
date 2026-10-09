# Installation

Use the shared DBA Tools deployment to run Monitor alongside Watchword, Rollcall,
and Muster. The suite installer builds both Monitor images and starts an empty
configuration in a persistent Docker volume. The default URL is
`http://localhost:3103`. Follow [the fresh suite installation](https://github.com/oorona/watchword/blob/main/docs/INSTALLATION.md), which creates one `.env` in the Watchword checkout and initializes the shared wallet.

The server needs Docker Engine, Compose v2, access to the four repositories, and
network/DNS access to the monitored systems. Node, Python, and Oracle software are
built into images. Monitor includes Oracle Client for Thick-mode shared wallet connections and uses unprivileged ICMP sockets.

## Standalone Docker

```bash
git clone git@github.com:oorona/monitor.git
cd monitor
cp servers.yaml.example servers.yaml
mkdir -p secrets
```

Configure Oracle targets in the shared registry with Monitor wallet access. Set
`DATABASE_REGISTRY_HOST_PATH` and `WALLET_HOST_PATH` to the exact same host directories used by Watchword and the other apps. Watchword must initialize the single shared wallet and add this account entry first.
Edit the example configuration and create a private secret file for each non-Oracle database
password reference, named `secrets/SECRET_NAME` or `secrets/SECRET_NAME.txt`. Secret
files must be readable by container UID 1000. Then start Docker:

```bash
docker compose --profile bootstrap run --rm --build mcp-init
docker compose up -d --build
```

Open `http://localhost:4000`. The Nginx gateway routes website requests to the frontend and `/mcp` to the
backend. The frontend proxies `/api/status` to the internal backend; the backend has no public port. Stop without deleting state with
`docker compose stop`.

## Local development

For local Oracle checks, install Oracle Client and configure ORACLE_CLIENT_LIB_DIR,
SUITE_REGISTRY_ROOT, and ORACLE_WALLET_ROOT. With Python 3.13 and Node 22 or later, install the pinned backend requirements and
frontend dependencies. Create `servers.yaml` and private secret files first.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MONITOR_SECRETS_PATH=../secrets uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```bash
cd frontend
npm ci
MONITOR_API_URL=http://127.0.0.1:8000 npm run dev
```

Open `http://localhost:3000`. On Linux the application group needs permission for
unprivileged ICMP sockets. Docker sets `net.ipv4.ping_group_range` for its own
network namespace automatically.

## Checks

```bash
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Backend tests require the backend dependencies plus pytest and pytest-asyncio:

```bash
python3 -m pip install -r backend/requirements.txt pytest pytest-asyncio
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

The suite has frontend, backend and gateway containers for Monitor. Read-only MCP uses a separate private bearer token; see [MCP](MCP.md).
