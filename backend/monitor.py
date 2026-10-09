import time
import logging
import psycopg2
import mysql.connector
import requests
from ping3 import ping
from typing import Dict, List, Any
from config import load_config, get_secret
from oracle_wallet import check_oracle, load_oracle_targets
from status_snapshot import publish, get_snapshot

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
                        if db_type == "pg":
                            db_status, db_error = check_postgres(host, port, db_name, user, password_secret)
                        elif db_type == "mysql":
                            db_status, db_error = check_mysql(host, port, db_name, user, password_secret)
                        else:
                            logger.warning(f"Unknown database type: {db_type}")
                            db_error = f"Unknown database type: {db_type}"

                        server_results["databases"][db_name] = {
                            "status": db_status,
                            "error": db_error,
                            "details": {k: v for k, v in details.items() if k != "password"}
                        }
                
                if not is_alive:
                    for db_name, details in databases.items():
                        server_results['databases'][db_name] = {
                            'status': None, 'error': 'Connection check skipped because host ICMP failed',
                            'details': {k: v for k, v in details.items() if k != 'password'},
                        }
                results["database"][env][server_name] = server_results

    # Oracle names, environments and wallet aliases come from the same registry
    # consumed by Watchword, Rollcall and Muster. Never derive an alias from a label.
    for database in load_oracle_targets():
        host = database.host or database.name
        environment = results['database'].setdefault(database.environment, {})
        if host not in environment:
            alive, error = check_ping(host) if database.host else (True, None)
            environment[host] = {'ping': alive, 'ping_error': error, 'databases': {}}
        server = environment[host]
        alias = database.access['monitor'].alias
        healthy, error = check_oracle(alias) if server['ping'] else (None, 'Connection check skipped because host ICMP failed')
        server['databases'][database.name] = {
            'status': healthy, 'error': error,
            'details': {'type': 'ora', 'database_id': str(database.id), 'auth_mode': 'wallet', 'alias': alias},
        }

    # Check Application Servers
    if "application" in config["servers"]:
        for env, servers in config["servers"]["application"].items():
            results["application"][env] = {}
            for server_name, details in servers.items():
                urls = list(details.get("urls", []))
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
                    "details": {k: v for k, v in details.items() if k != "password"}
                }
    
    publish(results)
    logger.info("Server poll completed.")

def get_status():
    """Returns the latest cached status."""
    return get_snapshot()["status"]
