import sys
import os
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Mock all dependencies before import
sys.modules['oracledb'] = MagicMock()
sys.modules['psycopg2'] = MagicMock()
sys.modules['mysql'] = MagicMock()
sys.modules['mysql.connector'] = MagicMock()
sys.modules['ping3'] = MagicMock()
sys.modules['yaml'] = MagicMock()
sys.modules['requests'] = MagicMock()

# Define test config
TEST_CONFIG = {
    "servers": {
        "database": {
            "production": {
                "server1": {
                    "ora_db": {"type": "ora", "port": 1521, "password": "s1"},
                    "pg_db": {"type": "pg", "password": "s2"}, # Default port 5432
                    "mysql_db": {"type": "mysql", "password": "s3"} # Default port 3306
                }
            }
        },
        "application": {
            "production": {
                "appserver1": {
                    "urls": ["https://site1.com"]
                }
            }
        }
    }
}

# Now we can import
from backend.monitor import poll_servers, get_status

def test_polling():
    print("Testing polling logic...")
    
    # Mock dependencies
    with patch('backend.monitor.ping') as mock_ping, \
         patch('backend.monitor.oracledb.connect') as mock_ora, \
         patch('backend.monitor.psycopg2.connect') as mock_pg, \
         patch('backend.monitor.mysql.connector.connect') as mock_mysql, \
         patch('backend.monitor.requests.get') as mock_get, \
         patch('backend.monitor.load_config') as mock_load_config, \
         patch('backend.monitor.get_secret') as mock_get_secret:
        
        # Setup mocks
        mock_ping.return_value = 0.1
        mock_ora.return_value.close = MagicMock()
        mock_pg.return_value.close = MagicMock()
        mock_mysql.return_value.close = MagicMock()
        mock_get.return_value.status_code = 200
        mock_load_config.return_value = TEST_CONFIG
        mock_get_secret.return_value = "secret_password"
        
        # Run poll
        poll_servers()
        
        # Check results
        status = get_status()
        print("Status result:", status)
        
        # Verify Database Structure
        server_status = status['database']['production']['server1']
        assert server_status['ping'] == True
        
        # Check Oracle
        assert server_status['databases']['ora_db']['status'] == True
        mock_ora.assert_called()
        
        # Check Postgres (default port)
        assert server_status['databases']['pg_db']['status'] == True
        args, kwargs = mock_pg.call_args
        assert kwargs['port'] == 5432
        
        # Check MySQL (default port)
        assert server_status['databases']['mysql_db']['status'] == True
        args, kwargs = mock_mysql.call_args
        assert kwargs['port'] == 3306
        
        print("Verification successful!")

if __name__ == "__main__":
    test_polling()
