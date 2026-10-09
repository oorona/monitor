FROM python:3.13.7-slim-bookworm AS oracle-client
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates unzip && rm -rf /var/lib/apt/lists/*
COPY oracle/ /build/oracle/
RUN python /build/oracle/install.py --architecture "$TARGETARCH"

FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends libaio1 libnsl2 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=oracle-client /opt/oracle/client/ /opt/oracle/client/
ENV LD_LIBRARY_PATH=/opt/oracle/client/lib ORACLE_CLIENT_LIB_DIR=/opt/oracle/client/lib
RUN python -c 'import oracledb; oracledb.init_oracle_client(); print(oracledb.clientversion())'
COPY *.py ./
USER 1000:1000
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
