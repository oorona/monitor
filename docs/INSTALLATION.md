# Installation Guide

## Prerequisites

### For Docker Deployment (Recommended)

- Docker Engine 20.10 or later
- Docker Compose v2 or later
- Network access to monitored servers
- ICMP ping capability (may require elevated privileges on some systems)

### For Local Development

#### Backend Requirements
- Python 3.11 or later
- pip (Python package manager)
- Oracle Instant Client (required for Oracle database monitoring)

#### Frontend Requirements
- Node.js 20 or later
- npm (Node package manager)

## Installation

### Docker Deployment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd monitor
   ```

2. Create your server configuration:
   ```bash
   cp servers.yaml.example servers.yaml
   ```

3. Create the secrets directory and add your credentials:
   ```bash
   mkdir -p secrets
   echo "your_password" > secrets/db_password_prod.txt
   echo "your_password" > secrets/db_password_test.txt
   ```

4. Build and start the containers:
   ```bash
   docker compose up -d --build
   ```

5. Access the application:
   - Frontend: http://localhost:4000
   - Backend API: http://localhost:9000

### Local Development

#### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install Oracle Instant Client (if monitoring Oracle databases):

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install libaio1
   wget https://download.oracle.com/otn_software/linux/instantclient/2112000/instantclient-basic-linux.x64-21.12.0.0.0dbru.zip
   unzip instantclient-basic-linux.x64-21.12.0.0.0dbru.zip -d /opt/oracle
   echo '/opt/oracle/instantclient_21_12' | sudo tee /etc/ld.so.conf.d/oracle-instantclient.conf
   sudo ldconfig
   ```

   **macOS:**
   ```bash
   # Download from Oracle website and extract to ~/instantclient_21_12
   export DYLD_LIBRARY_PATH=~/instantclient_21_12:$DYLD_LIBRARY_PATH
   ```

5. Start the backend server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

#### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Access the frontend at http://localhost:3000

## Verification

### Verify Backend

```bash
curl http://localhost:9000/health
# Expected response: {"status":"ok"}

curl http://localhost:9000/status
# Expected response: JSON with server status data
```

### Verify Frontend

Open http://localhost:4000 (Docker) or http://localhost:3000 (local) in a browser. You should see the Server Monitor dashboard.

## Running Tests

```bash
python verify_local.py
```

## Stopping Services

### Docker
```bash
docker compose down
```

### Local Development
Press `Ctrl+C` in each terminal running the backend and frontend servers.
