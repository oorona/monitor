"""One fresh Oracle SEPS login; no application-supplied database password."""
import json
import sys
import oracledb


def check(config):
    oracledb.init_oracle_client(lib_dir=config.get('client_lib_dir'), config_dir=config['wallet_dir'])
    with oracledb.connect(dsn=config['alias'], externalauth=True) as connection:
        connection.call_timeout = 5000
        connection.module = 'monitor'
        with connection.cursor() as cursor:
            cursor.execute("SELECT SYS_CONTEXT('USERENV','SESSION_USER'), SYS_CONTEXT('USERENV','AUTHENTICATED_IDENTITY') FROM dual")
            if any(str(value).upper() in {'SYS', 'SYSTEM'} for value in cursor.fetchone()):
                raise ValueError('Administrative accounts are forbidden for Monitor targets')
            cursor.execute('SELECT 1 FROM dual')
            if cursor.fetchone()[0] != 1:
                raise ValueError('Oracle health query failed')
    return {'ok': True}


def main():
    try:
        result = check(json.load(sys.stdin))
    except Exception:
        # Do not return vendor diagnostics that might echo connection information.
        result = {'ok': False, 'error': 'Oracle wallet login or health query failed; verify alias, account and network access'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
