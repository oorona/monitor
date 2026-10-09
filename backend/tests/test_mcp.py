import asyncio
from datetime import UTC,datetime,timedelta
import json
import socket
import threading
import time
import httpx2 as httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
import status_snapshot
from mcp_auth import initialize, read_token, MonitorTokenVerifier
from mcp_server import services, page

DATA = {'database': {'prod': {'db.internal': {'ping':False, 'databases': {
    'canonical-db': {'status':None,'error':'password-secret-fixture','details':{'type':'ora','database_id':'stable-id','password':'password-secret-fixture','username':'secret-user','alias':'private-wallet'}},
}}}}, 'application': {'prod': {'web': {'ping':True,'urls': {
    'https://user:password-secret-fixture@web.internal/health?token=private-query': {'status':False,'error':'Status code: 503'},
    'https://healthy.internal/health': {'status':True,'error':None},
}}},'test': {'test-web': {'ping':True,'urls': {'https://test.internal/health':{'status':True,'error':None}}}}}}

@pytest.fixture(autouse=True)
def snapshot(monkeypatch):
    monkeypatch.setattr(status_snapshot,'_state',{'status':{},'updated_at':None,'last_attempt_at':None,'poll_error':False})


def test_snapshot_reports_initializing_current_failure_and_stale(monkeypatch):
    assert status_snapshot.get_snapshot()['metadata']['state']=='initializing'
    status_snapshot.begin_poll();status_snapshot.publish(DATA)
    first=status_snapshot.get_snapshot()
    assert first['metadata']['state']=='current' and first['metadata']['updated_at']
    status_snapshot.fail_poll()
    assert status_snapshot.get_snapshot()['metadata']['state']=='stale'
    assert status_snapshot.get_snapshot()['status']==DATA
    status_snapshot.publish(DATA)
    status_snapshot._state['updated_at']=datetime.now(UTC)-timedelta(seconds=121)
    assert status_snapshot.get_snapshot()['metadata']['state']=='stale'


def test_safe_status_fields_and_unknown_database_check():
    status_snapshot.publish(DATA)
    output=page(environment='PROD')
    assert output['total']==5
    text=json.dumps(output)
    for secret in ('password-secret-fixture','private-query','secret-user','private-wallet'):
        assert secret not in text
    db=next(r for r in output['services'] if r['kind']=='database')
    assert db['state']=='unknown' and db['database_id']=='stable-id'
    http=next(r for r in output['services'] if r['state']=='unhealthy' and r['kind']=='http')
    assert http['name']=='https://web.internal/health' and http['error']=='Status code: 503'
    assert page(environment='test')['total']==2
    assert page(query='CANONICAL',kind='database')['total']==1
    assert len(page(limit=1,offset=1)['services'])==1


def test_token_initializer_preserves_existing_private_token_and_refuses_symlink(tmp_path):
    destination=tmp_path/'auth';initialize(destination)
    token=read_token(destination/'token');initialize(destination)
    assert read_token(destination/'token')==token
    assert (destination/'token').stat().st_mode & 0o777 == 0o600
    assert destination.stat().st_mode & 0o777 == 0o700
    link=tmp_path/'link';link.symlink_to(destination)
    with pytest.raises(ValueError):initialize(link)


@pytest.mark.asyncio
async def test_auth_fails_closed_and_observes_token_rotation(tmp_path,monkeypatch):
    monkeypatch.setenv('MONITOR_MCP_TOKEN_FILE',str(tmp_path/'token'))
    verifier=MonitorTokenVerifier()
    assert await verifier.verify_token('invalid') is None
    initialize(tmp_path)
    token=read_token(tmp_path/'token')
    assert (await verifier.verify_token(token)).scopes==['status:read']
    assert await verifier.verify_token('wrong') is None
    (tmp_path/'token').write_text('monitor_'+'x'*43)
    assert await verifier.verify_token(token) is None


@pytest.fixture
def server(tmp_path,monkeypatch):
    (tmp_path/'servers.yaml').write_text('servers: {database: {}, application: {}}')
    monkeypatch.setenv('MONITOR_CONFIG_PATH',str(tmp_path/'servers.yaml'))
    monkeypatch.setenv('MONITOR_MCP_TOKEN_FILE',str(tmp_path/'auth/token'))
    monkeypatch.delenv('SUITE_REGISTRY_ROOT',raising=False)
    initialize(tmp_path/'auth')
    import main
    async def no_poll():await asyncio.Event().wait()
    monkeypatch.setattr(main,'background_poller',no_poll)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    instance=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=port,log_level='warning',lifespan='on'))
    thread=threading.Thread(target=instance.run,daemon=True);thread.start()
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                if httpx.get(base+'/health').status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.05)
        else:raise AssertionError('MCP test server failed to start')
        status_snapshot.publish(DATA)
        yield {'url':base+'/mcp','base':base,'token':read_token(tmp_path/'auth/token')}
    finally:
        instance.should_exit=True;thread.join(10)
        assert not thread.is_alive()


@pytest.mark.asyncio
async def test_real_http_mcp_handshake_tools_paging_and_freshness(server):
    async with Client(server['url'],auth=BearerAuth(server['token'])) as client:
        tools=await client.list_tools()
        assert {t.name for t in tools}=={'get_monitor_summary','list_services','list_problems','get_service_status'}
        assert all(t.annotations.read_only_hint for t in tools)
        summary=(await client.call_tool('get_monitor_summary',{'environment':'prod'})).data
        assert summary['counts']=={'healthy':2,'unhealthy':2,'unknown':1}
        assert summary['snapshot']['state']=='current'
        result=(await client.call_tool('list_services',{'query':'canonical','limit':1})).data
        record=result['services'][0]
        detail=(await client.call_tool('get_service_status',{'service_id':record['id']})).data
        assert detail['service']['state']=='unknown'
        problems=(await client.call_tool('list_problems',{'environment':'prod'})).data
        assert problems['total']==3
        assert (await client.call_tool('list_services',{'limit':201},raise_on_error=False)).is_error
        assert (await client.call_tool('get_service_status',{'service_id':'missing'},raise_on_error=False)).is_error
        status_snapshot.fail_poll()
        assert (await client.call_tool('get_monitor_summary',{})).data['snapshot']['state']=='stale'
    assert httpx.get(server['base']+'/status').json()==DATA


@pytest.mark.asyncio
async def test_http_mcp_auth_host_origin_guards_and_no_token_leaks(server):
    payload={'jsonrpc':'2.0','id':1,'method':'tools/list'}
    headers={'Accept':'application/json, text/event-stream'}
    with httpx.Client() as api:
        for bearer in (None,'invalid'):
            h=headers | ({'Authorization':'Bearer '+bearer} if bearer else {})
            response=api.post(server['url'],json=payload,headers=h)
            assert response.status_code==401 and server['token'] not in response.text
        h=headers | {'Authorization':'Bearer '+server['token']}
        assert api.post(server['url'],json=payload,headers=h|{'Host':'evil.example'}).status_code==421
        assert api.post(server['url'],json=payload,headers=h|{'Origin':'https://evil.example'}).status_code==403


def test_poller_keeps_skipped_databases_as_unknown(monkeypatch):
    import monitor
    from types import SimpleNamespace
    monkeypatch.setattr(monitor,'load_config',lambda:{'servers':{'database':{'prod':{'db.internal':{
        'pgdb':{'type':'pg','username':'reader','password':'private'},
    }}}}})
    monkeypatch.setattr(monitor,'load_oracle_targets',lambda:[SimpleNamespace(host='db.internal',environment='prod',name='canonical-db',id='stable-id',access={'monitor':SimpleNamespace(alias='reader')})])
    monkeypatch.setattr(monitor,'check_ping',lambda host:(False,'timeout'))
    def forbidden(*args):raise AssertionError('Database connection must be skipped after ICMP failure')
    monkeypatch.setattr(monitor,'check_oracle',forbidden)
    monkeypatch.setattr(monitor,'check_postgres',forbidden)
    monitor.poll_servers()
    databases=monitor.get_status()['database']['prod']['db.internal']['databases']
    assert databases['pgdb']['status'] is None and databases['canonical-db']['status'] is None
    assert 'password' not in databases['pgdb']['details']
    assert status_snapshot.get_snapshot()['metadata']['state']=='current'


@pytest.mark.asyncio
async def test_background_poll_failure_marks_previous_results_stale(monkeypatch):
    import main
    status_snapshot.publish(DATA)
    def fail():raise ValueError('private diagnostic')
    async def stop(*args):raise asyncio.CancelledError
    monkeypatch.setattr(main,'poll_servers',fail)
    monkeypatch.setattr(main.asyncio,'sleep',stop)
    with pytest.raises(asyncio.CancelledError):await main.background_poller()
    snapshot=status_snapshot.get_snapshot()
    assert snapshot['metadata']['state']=='stale' and snapshot['metadata']['poll_error']
    assert snapshot['status']==DATA
