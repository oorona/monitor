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

## Secrets Management

### Docker Secrets (Recommended)

Docker secrets are mounted at `/run/secrets/<secret_name>`. Create secret files in the `secrets/` directory:

```bash
mkdir -p secrets
echo "your_secure_password" > secrets/db_password_prod.txt
echo "test_password" > secrets/db_password_test.txt
```

Define secrets in `docker-compose.yml`:

```yaml
secrets:
  db_password_prod:
    file: ./secrets/db_password_prod.txt
  db_password_test:
    file: ./secrets/db_password_test.txt
```

### Environment Variables (Fallback)

If a Docker secret is not found, the system falls back to environment variables. The secret name is converted to uppercase:

```bash
export DB_PASSWORD_PROD="your_secure_password"
export DB_PASSWORD_TEST="test_password"
```

## Environment Variables

### Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONUNBUFFERED` | `1` | Ensures real-time log output |

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:9000` | Backend API endpoint |
| `NEXT_PUBLIC_REFRESH_INTERVAL` | `30000` | Auto-refresh interval in milliseconds |
| `NODE_ENV` | - | Set to `production` for container builds |

### Setting Environment Variables

#### In Docker Compose

```yaml
services:
  frontend:
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
      - NEXT_PUBLIC_REFRESH_INTERVAL=60000
```

#### For Local Development

```bash
export NEXT_PUBLIC_API_URL=http://localhost:8000
export NEXT_PUBLIC_REFRESH_INTERVAL=15000
npm run dev
```

## Docker Compose Configuration

### Port Mapping

| Service | Container Port | Host Port |
|---------|----------------|-----------|
| Backend | 8000 | 9000 |
| Frontend | 3000 | 4000 |

### Modifying Ports

Edit `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8080:8000"  # Change host port to 8080
  frontend:
    ports:
      - "3000:3000"  # Change host port to 3000
```

### Volume Mounts

The `servers.yaml` configuration file is mounted into the backend container:

```yaml
volumes:
  - ./servers.yaml:/app/servers.yaml
```

## Polling Configuration

### Polling Interval

The backend polls all servers every 60 seconds. To modify this, edit `backend/main.py`:

```python
# Change from 60 to desired interval in seconds
await asyncio.sleep(60)
```

### Connection Timeouts

| Check Type | Timeout | File |
|------------|---------|------|
| Ping | 2 seconds | `backend/monitor.py` |
| Database | 5 seconds | `backend/monitor.py` |
| HTTP URL | 10 seconds | `backend/monitor.py` |

To modify timeouts, edit the respective check functions in `backend/monitor.py`.

## Security Considerations

1. **Never commit secrets** - The `secrets/` directory and `servers.yaml` are in `.gitignore`
2. **Restrict CORS in production** - Update `backend/main.py` to specify allowed origins
3. **Use HTTPS** - Place a reverse proxy (nginx, Traefik) in front of the services
4. **Network isolation** - Run in a private network with controlled access
