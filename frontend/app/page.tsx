'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { Icon } from '../components/Icon';
import type { StatusResponse } from './types';

type Row = { kind: string; environment: string; host: string; service: string; healthy: boolean | null; error?: string; ping: boolean };
export default function Home() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [view, setView] = useState('Overview');
  const [query, setQuery] = useState('');
  const [environment, setEnvironment] = useState('all');
  const pending = useRef(false);
  const fetchStatus = useCallback(async () => {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    try {
      const response = await fetch('/api/status', { cache: 'no-store', signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error('Monitor is unavailable. Try refreshing shortly.');
      setStatus(await response.json());
      setLastUpdated(new Date());
      setError(null);
    } catch {
      setError('Could not refresh server status. Any displayed results are from the last successful refresh.');
    } finally { pending.current = false; setLoading(false); }
  }, []);
  useEffect(() => {
    const initial = setTimeout(() => void fetchStatus(), 0);
    const interval = autoRefresh ? setInterval(() => void fetchStatus(), 30000) : undefined;
    return () => { clearTimeout(initial); if (interval) clearInterval(interval); };
  }, [autoRefresh, fetchStatus]);
  const rows = useMemo(() => {
    const result: Row[] = [];
    for (const [env, servers] of Object.entries(status?.database || {})) {
      for (const [host, server] of Object.entries(servers)) {
        const databases = Object.entries(server.databases);
        if (!databases.length) result.push({ kind: 'Database', environment: env, host, service: 'Host reachability', healthy: false, error: server.ping_error, ping: server.ping });
        for (const [name, db] of databases) result.push({ kind: 'Database', environment: env, host, service: name, healthy: db.status, error: db.error, ping: server.ping });
      }
    }
    for (const [env, servers] of Object.entries(status?.application || {})) {
      for (const [host, server] of Object.entries(servers)) {
        for (const [url, check] of Object.entries(server.urls)) result.push({ kind: 'Application', environment: env, host, service: url, healthy: check.status, error: check.error, ping: server.ping });
      }
    }
    return result;
  }, [status]);
  const environments = [...new Set(rows.map(row => row.environment))];
  const visible = rows.filter(row => (view === 'Overview' || row.kind === (view === 'Databases' ? 'Database' : 'Application')) && (environment === 'all' || row.environment === environment) && `${row.host} ${row.service} ${row.environment}`.toLowerCase().includes(query.toLowerCase()));
  const healthy = rows.filter(row => row.healthy).length;
  const waiting = status && !('database' in status);
  return <div className="flex min-h-screen flex-col md:flex-row">
    <nav className="suite-nav flex shrink-0 items-center gap-1 overflow-x-auto px-3 py-3 md:sticky md:top-0 md:h-screen md:w-[230px] md:flex-col md:items-stretch md:px-[23px] md:py-[33px]" aria-label="Main">
      <Link href="/" className="suite-wordmark mr-4 flex items-center gap-3 px-2 md:mb-9 md:mr-0"><span className="text-accent" aria-hidden="true">◈</span>Monitor</Link>
      <p className="mb-3 hidden px-3 text-[10px] uppercase tracking-[.18em] text-muted md:block">Infrastructure workspace</p>
      {['Overview', 'Databases', 'Applications'].map((name, index) => <button key={name} aria-current={view === name ? 'page' : undefined} onClick={() => setView(name)} className="suite-nav-link flex items-center gap-3 whitespace-nowrap rounded-md px-3 py-3 text-left text-[13px]"><Icon name={['grid', 'database', 'pulse'][index]} />{name}</button>)}
      <div className="mt-auto hidden rounded-xl border border-line p-3 text-xs text-muted md:block"><div className="mb-2 flex items-center gap-2 text-accent"><Icon name="pulse" size={15} />Continuous monitoring</div>Database connectivity and application health, in one workspace.</div>
    </nav>
    <main className="min-w-0 flex-1">
      <header className="flex h-[66px] items-center justify-between border-b border-line bg-panel-2 px-5 text-xs text-muted md:px-10"><span>Monitor <span className="px-3" aria-hidden="true">/</span> {view}</span><span>Infrastructure health</span></header>
      <div className="suite-main p-5 md:p-10">
        <div className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow mb-3">Infrastructure workspace</p><h1>{view === 'Overview' ? 'Server health' : view}</h1><p className="mt-3 text-sm text-muted">Connection checks across your database and application servers.</p></div><div className="flex flex-wrap items-center gap-3"><label className="flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />Auto refresh</label><button className="btn" disabled={loading} onClick={() => void fetchStatus()}><Icon name="pulse" size={16} />{loading ? 'Refreshing…' : 'Refresh'}</button></div></div>
        {error && <div role="alert" className="mb-5 rounded-lg border border-crit bg-crit-bg p-4 text-sm text-crit">{error}</div>}
        <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[['Services', rows.length, 'Configured checks'], ['Healthy', healthy, 'Successful connections'], ['Needs attention', rows.length - healthy, 'Failed or skipped checks'], ['Environments', environments.length, 'Monitored environments']].map(([label, value, note]) => <div key={label} className="metric-card"><p className="text-xs text-muted">{label}</p><p className="my-3 font-serif text-4xl">{value}</p><p className="text-xs text-muted">{note}</p></div>)}</div>
        <section className="card overflow-hidden" aria-label="Service health"><div className="flex flex-wrap items-center justify-between gap-4 border-b border-line p-5"><div><h2 className="font-semibold">Service status</h2><p className="mt-1 text-xs text-muted">{visible.length} checks · {lastUpdated ? `Last refreshed ${lastUpdated.toLocaleTimeString()}` : 'Awaiting first refresh'}</p></div><div className="flex flex-wrap gap-2"><input className="input w-auto" aria-label="Search servers and services" placeholder="Search servers or services…" value={query} onChange={e => setQuery(e.target.value)} /><select className="input w-auto" aria-label="Filter environment" value={environment} onChange={e => setEnvironment(e.target.value)}><option value="all">All environments</option>{environments.map(env => <option key={env}>{env}</option>)}</select></div></div>
        {!visible.length ? <div className="p-12 text-center text-sm text-muted">{loading ? 'Loading server status…' : waiting ? 'The first server poll is in progress. Results will appear shortly.' : rows.length ? 'No services match these filters.' : 'No monitored services yet. Import your configuration to start monitoring.'}</div> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-panel-2 text-xs text-muted"><tr>{['Server / service', 'Environment', 'Type', 'Network', 'Status'].map(label => <th key={label} className="px-5 py-3 font-medium">{label}</th>)}</tr></thead><tbody>{visible.map(row => <tr key={`${row.kind}/${row.environment}/${row.host}/${row.service}`} className="border-t border-line"><td className="max-w-md px-5 py-4"><p className="font-medium">{row.host}</p><p className="mt-1 break-all text-xs text-muted">{row.kind === 'Application' ? <a href={row.service} target="_blank" rel="noopener noreferrer" className="link">{row.service}</a> : row.service}</p>{row.error && <p className="mt-2 break-words text-xs text-crit">{row.error}</p>}</td><td className="px-5 py-4"><span className="chip">{row.environment}</span></td><td className="px-5 py-4 text-muted">{row.kind}</td><td className="px-5 py-4 text-xs text-muted">{row.ping ? 'Reachable' : 'Ping failed'}</td><td className="px-5 py-4"><span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-2 py-1 text-xs font-medium ${row.healthy ? 'bg-ok-bg text-ok' : 'bg-crit-bg text-crit'}`}><Icon name={row.healthy ? 'check' : 'alert'} size={14} />{row.healthy === null ? 'Not checked' : row.healthy ? 'Healthy' : 'Needs attention'}</span></td></tr>)}</tbody></table></div>}</section>
      </div>
    </main>
  </div>;
}
