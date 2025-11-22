FROM python:3.11-slim-bullseye

# Install system dependencies for Oracle Instant Client
RUN apt-get update && apt-get install -y \
    libaio1 \
    libpq-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Oracle Instant Client
WORKDIR /opt/oracle
RUN wget https://download.oracle.com/otn_software/linux/instantclient/2112000/instantclient-basic-linux.x64-21.12.0.0.0dbru.zip && \
    unzip instantclient-basic-linux.x64-21.12.0.0.0dbru.zip && \
    rm instantclient-basic-linux.x64-21.12.0.0.0dbru.zip && \
    sh -c "echo /opt/oracle/instantclient_21_12 > /etc/ld.so.conf.d/oracle-instantclient.conf" && \
    ldconfig

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
