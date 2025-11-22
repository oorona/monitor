import time
import logging
import oracledb
import psycopg2
import mysql.connector
import requests
from ping3 import ping
from typing import Dict, List, Any
from config import load_config, get_secret

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state to store server statuses
server_status_cache = {}

def check_ping(host: str) -> (bool, str):
    """Pings a host to check if it's reachable."""
    try:
        response = ping(host, timeout=2)
        if response is not None and response is not False:
            return True, None
        return False, "Ping returned None or False"
    except Exception as e:
        logger.error(f"Ping failed for {host}: {e}")
        return False, str(e)

def check_oracle(host: str, port: int, dbname: str, user: str, password_secret_name: str) -> (bool, str):
    """Checks connection to an Oracle database."""
    password = get_secret(password_secret_name)
    if not password:
        return False, "Password not found"
    
    # Default port for Oracle
    if not port:
        port = 1521

    dsn = f"{host}:{port}/{dbname}"
    try:
        connection = oracledb.connect(user=user, password=password, dsn=dsn, timeout=5)
        connection.close()
        return True, None
    except Exception as e:
        logger.error(f"Oracle connection failed for {dsn}: {e}")
        return False, str(e)

def check_postgres(host: str, port: int, dbname: str, user: str, password_secret_name: str) -> (bool, str):
    """Checks connection to a PostgreSQL database."""
    password = get_secret(password_secret_name)
    if not password:
        return False, "Password not found"

    # Default port for Postgres
    if not port:
        port = 5432

    try:
        connection = psycopg2.connect(
            host=host,
            port=port,
            database=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        connection.close()
        return True, None
    except Exception as e:
        logger.error(f"Postgres connection failed for {host}:{port}/{dbname}: {e}")
        return False, str(e)

def check_mysql(host: str, port: int, dbname: str, user: str, password_secret_name: str) -> (bool, str):
    """Checks connection to a MySQL database."""
    password = get_secret(password_secret_name)
    if not password:
        return False, "Password not found"

    # Default port for MySQL
    if not port:
        port = 3306

    try:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            database=dbname,
            user=user,
            password=password,
            connection_timeout=5
        )
        connection.close()
        return True, None
    except Exception as e:
        logger.error(f"MySQL connection failed for {host}:{port}/{dbname}: {e}")
        return False, str(e)

def check_url(url: str) -> (bool, str):
    """Checks if a URL is reachable, following redirects."""
    try:
        response = requests.get(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            return True, None
        return False, f"Status code: {response.status_code}"
    except requests.RequestException as e:
        logger.error(f"URL check failed for {url}: {e}")
        return False, str(e)

def poll_servers():
    """Polls all servers defined in the configuration and updates status."""
    config = load_config()
    results = {
        "database": {},
        "application": {}
    }

    # Check Database Servers
    if "database" in config["servers"]:
        for env, servers in config["servers"]["database"].items():
            results["database"][env] = {}
            
            for server_name, databases in servers.items():
                host = server_name
                is_alive, ping_error = check_ping(host)
                
                server_results = {
                    "ping": is_alive,
                    "ping_error": ping_error,
                    "databases": {}
                }

                if is_alive:
                    for db_name, details in databases.items():
                        db_type = details.get("type", "ora") # Default to ora if missing? Or error?
                        port = details.get("port")
                        user = details.get("username")
                        password_secret = details.get("password")
                        
                        db_status = False
                        db_error = None
                        if db_type == "ora":
                            db_status, db_error = check_oracle(host, port, db_name, user, password_secret)
                        elif db_type == "pg":
                            db_status, db_error = check_postgres(host, port, db_name, user, password_secret)
                        elif db_type == "mysql":
                            db_status, db_error = check_mysql(host, port, db_name, user, password_secret)
                        else:
                            logger.warning(f"Unknown database type: {db_type}")
                            db_error = f"Unknown database type: {db_type}"

                        server_results["databases"][db_name] = {
                            "status": db_status,
                            "error": db_error,
                            "details": details
                        }
                
                results["database"][env][server_name] = server_results

    # Check Application Servers
    if "application" in config["servers"]:
        for env, servers in config["servers"]["application"].items():
            results["application"][env] = {}
            for server_name, details in servers.items():
                urls = details.get("urls", [])
                if "url" in details:
                    urls.append(details["url"])
                
                host = server_name
                if urls:
                    try:
                        host = urls[0].split("//")[-1].split("/")[0].split(":")[0]
                    except:
                        pass

                is_alive, ping_error = check_ping(host)
                
                url_statuses = {}
                for url in urls:
                    status, error = check_url(url)
                    url_statuses[url] = {
                        "status": status,
                        "error": error
                    }
                
                results["application"][env][server_name] = {
                    "ping": is_alive,
                    "ping_error": ping_error,
                    "urls": url_statuses,
                    "details": details
                }
    
    global server_status_cache
    server_status_cache = results
    logger.info("Server poll completed.")

def get_status():
    """Returns the latest cached status."""
    return server_status_cache
