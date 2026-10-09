"""Read-only MCP tools over the same completed status snapshot as the dashboard."""
import hashlib
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from mcp_auth import MonitorTokenVerifier
from status_snapshot import get_snapshot

TextFilter = Annotated[str | None, Field(max_length=200)]
Limit = Annotated[int, Field(ge=1, le=200)]
Offset = Annotated[int, Field(ge=0, le=100000)]
Kind = Literal['host', 'database', 'http']
State = Literal['healthy', 'unhealthy', 'unknown']
INSTRUCTIONS = '''Answer service-status questions using the latest completed Monitor poll.
Always report the snapshot timestamp and freshness. An initializing, stale or failed
poll does not establish current health; an empty result does not establish that
all configured services are healthy. A failed host ping does not prove its database
is down: skipped database checks are unknown. Results are observations, not root
cause diagnoses. Tools never refresh targets, execute SQL, or change configuration.
No history is stored; do not infer outage duration from a single snapshot.'''


def safe_url(value):
    url = urlsplit(value)
    host = url.hostname or ''
    if ':' in host:
        host = f'[{host}]'
    try:
        if url.port:
            host += f':{url.port}'
    except ValueError:
        pass
    return urlunsplit((url.scheme, host, url.path, '', ''))


def _state(value):
    return 'healthy' if value is True else 'unhealthy' if value is False else 'unknown'


def services(status):
    records = []
    for group, environments in status.items():
        if group not in ('database', 'application'):
            continue
        for environment, hosts in environments.items():
            for host, result in hosts.items():
                base = {'environment': environment, 'host': host}
                records.append(base | {'id': f'host/{group}/{environment}/{host}', 'kind': 'host', 'name': host,
                    'state': _state(result.get('ping')), 'error': None if result.get('ping') else 'Host ICMP check failed'})
                if group == 'database':
                    for name, database in result.get('databases', {}).items():
                        details = database.get('details', {})
                        value = database.get('status')
                        records.append(base | {'id': f'database/{environment}/{host}/{name}', 'kind': 'database', 'name': name,
                            'database_id': details.get('database_id'), 'database_type': details.get('type'),
                            'state': _state(value), 'error': None if value is True else (
                                'Connection check skipped because host ICMP failed' if value is None else 'Database connection check failed')})
                else:
                    for url, http in result.get('urls', {}).items():
                        value = http.get('status')
                        diagnostic = http.get('error') or ''
                        records.append(base | {'id': f'http/{environment}/{host}/'+hashlib.sha256(url.encode()).hexdigest()[:16],
                            'kind': 'http', 'name': safe_url(url), 'state': _state(value),
                            'error': None if value is True else diagnostic if re.fullmatch(r'Status code: \d{3}', diagnostic) else 'HTTP health check failed'})
    return sorted(records, key=lambda r: (r['environment'], r['kind'], r['host'], r['name']))


def filtered(records, environment=None, query=None, kind=None, state=None):
    return [r for r in records if (environment is None or r['environment'].casefold() == environment.casefold())
            and (kind is None or r['kind'] == kind) and (state is None or r['state'] == state)
            and (query is None or query.casefold() in ' '.join(str(r.get(k) or '') for k in ('name','host','id','database_id')).casefold())]


def page(environment=None, query=None, kind=None, state=None, limit=100, offset=0, problems=False):
    snapshot = get_snapshot()
    records = filtered(services(snapshot['status']), environment, query, kind, state)
    if problems:
        records = [r for r in records if r['state'] != 'healthy']
    return {'snapshot': snapshot['metadata'], 'total': len(records), 'offset': offset,
            'limit': limit, 'services': records[offset:offset + limit]}


def build_mcp():
    mcp = FastMCP('monitor', instructions=INSTRUCTIONS, auth=MonitorTokenVerifier(), mask_error_details=True)
    annotations = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False}

    @mcp.tool(annotations=annotations)
    def get_monitor_summary(environment: TextFilter = None) -> dict:
        """Summarize current host, database and HTTP checks; include snapshot freshness and environment names."""
        snapshot = get_snapshot()
        records = filtered(services(snapshot['status']), environment)
        counts = {state: sum(r['state'] == state for r in records) for state in ('healthy','unhealthy','unknown')}
        return {'snapshot': snapshot['metadata'], 'total': len(records), 'counts': counts,
                'by_kind': {kind: {state: sum(r['kind'] == kind and r['state'] == state for r in records)
                            for state in counts} for kind in ('host','database','http')},
                'environments': sorted({r['environment'] for r in services(snapshot['status'])})}

    @mcp.tool(annotations=annotations)
    def list_services(environment: TextFilter = None, query: TextFilter = None, kind: Kind | None = None,
                      state: State | None = None, limit: Limit = 100, offset: Offset = 0) -> dict:
        """Find monitored services by environment, database/service/host name, UUID, kind or health; results are paginated."""
        return page(environment, query, kind, state, limit, offset)

    @mcp.tool(annotations=annotations)
    def list_problems(environment: TextFilter = None, kind: Kind | None = None,
                      limit: Limit = 100, offset: Offset = 0) -> dict:
        """List failed or unknown checks, including checks skipped after ICMP failure. Inspect snapshot freshness."""
        return page(environment=environment, kind=kind, limit=limit, offset=offset, problems=True)

    @mcp.tool(annotations=annotations)
    def get_service_status(service_id: Annotated[str, Field(min_length=1, max_length=2000)]) -> dict:
        """Get one exact service ID returned by list_services; include its latest observed state and freshness."""
        snapshot = get_snapshot()
        record = next((r for r in services(snapshot['status']) if r['id'] == service_id), None)
        if record is None:
            raise ToolError('Service not found in the latest snapshot; use list_services to find its exact ID')
        return {'snapshot': snapshot['metadata'], 'service': record}

    return mcp
