'use client';

import { useEffect, useState } from 'react';
import { StatusResponse, EnvironmentDatabaseGroup, EnvironmentApplicationGroup, ServerDatabaseStatus, ApplicationStatus } from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9000';

const REFRESH_INTERVAL = Number(process.env.NEXT_PUBLIC_REFRESH_INTERVAL) || 30000;

export default function Home() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/status`);
      if (!res.ok) {
        throw new Error('Failed to fetch status');
      }
      const data: StatusResponse = await res.json();
      setStatus(data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError('Error fetching server status');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    if (!autoRefresh) return;

    const interval = setInterval(fetchStatus, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (loading && !status) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
        <div className="animate-pulse">Loading status...</div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-8 font-sans">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
              Server Monitor
            </h1>
            <p className="text-gray-400 mt-2">Real-time infrastructure status</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                <span className="ml-3 text-sm font-medium text-gray-300">Auto Refresh</span>
              </label>
            </div>
            <div className="text-right">
              <div className="text-sm text-gray-500">Last Updated</div>
              <div className="font-mono text-blue-400">
                {lastUpdated ? lastUpdated.toLocaleTimeString() : '-'}
              </div>
            </div>
          </div>
        </header>

        {error && (
          <div className="bg-red-900/50 border border-red-500 text-red-200 p-4 rounded-lg mb-8">
            {error}
          </div>
        )}

        {status && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Database Section */}
            {status.database && (
              <Section title="Databases" icon="🗄️">
                {Object.entries(status.database).map(([env, servers]) => (
                  <DatabaseEnvironmentGroup key={env} name={env} servers={servers} />
                ))}
              </Section>
            )}

            {/* Application Section */}
            {status.application && (
              <Section title="Applications" icon="🚀">
                {Object.entries(status.application).map(([env, servers]) => (
                  <ApplicationEnvironmentGroup key={env} name={env} servers={servers} />
                ))}
              </Section>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700 backdrop-blur-sm">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2 text-white">
        <span>{icon}</span> {title}
      </h2>
      <div className="space-y-6">
        {children}
      </div>
    </div>
  );
}

function DatabaseEnvironmentGroup({ name, servers }: { name: string; servers: EnvironmentDatabaseGroup }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3 ml-1">
        {name}
      </h3>
      <div className="grid gap-3">
        {Object.entries(servers).map(([serverName, status]) => (
          <DatabaseServerCard key={serverName} name={serverName} status={status} />
        ))}
      </div>
    </div>
  );
}

function ApplicationEnvironmentGroup({ name, servers }: { name: string; servers: EnvironmentApplicationGroup }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3 ml-1">
        {name}
      </h3>
      <div className="grid gap-3">
        {Object.entries(servers).map(([serverName, status]) => (
          <ApplicationServerCard key={serverName} name={serverName} status={status} />
        ))}
      </div>
    </div>
  );
}

function DatabaseServerCard({ name, status }: { name: string; status: ServerDatabaseStatus }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
      <div className="flex justify-between items-start mb-2">
        <h4 className="font-medium text-white">{name}</h4>
        <div className="flex items-center gap-2">
          {status.ping_error && (
            <span className="text-xs text-red-400" title={status.ping_error}>
              ⚠️ {status.ping_error}
            </span>
          )}
          <StatusBadge label="PING" active={status.ping} />
        </div>
      </div>

      {status.ping && (
        <div className="mt-2 space-y-2 pl-2 border-l-2 border-gray-700">
          {Object.entries(status.databases).map(([dbName, dbStatus]) => (
            <div key={dbName} className="flex justify-between items-center text-sm">
              <span className="text-gray-300">{dbName}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">
                  {dbStatus.details.username}@{dbStatus.details.port}
                </span>
                {!dbStatus.status && dbStatus.error && (
                  <span className="text-xs text-red-400 truncate max-w-[150px]" title={dbStatus.error}>
                    {dbStatus.error}
                  </span>
                )}
                <StatusBadge label="DB" active={dbStatus.status} small />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ApplicationServerCard({ name, status }: { name: string; status: ApplicationStatus }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
      <div className="flex justify-between items-start mb-2">
        <h4 className="font-medium text-white">{name}</h4>
        <div className="flex items-center gap-2">
          {status.ping_error && (
            <span className="text-xs text-red-400" title={status.ping_error}>
              ⚠️ {status.ping_error}
            </span>
          )}
          <StatusBadge label="PING" active={status.ping} />
        </div>
      </div>

      <div className="mt-2 space-y-2 pl-2 border-l-2 border-gray-700">
        {Object.entries(status.urls).map(([url, urlStatus]) => (
          <div key={url} className="flex justify-between items-center text-sm">
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline truncate max-w-[200px]">
              {url}
            </a>
            <div className="flex items-center gap-2">
              {!urlStatus.status && urlStatus.error && (
                <span className="text-xs text-red-400 truncate max-w-[150px]" title={urlStatus.error}>
                  {urlStatus.error}
                </span>
              )}
              <StatusBadge label={urlStatus.status ? "200 OK" : "ERROR"} active={urlStatus.status} small />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ label, active, small }: { label: string; active: boolean; small?: boolean }) {
  return (
    <div className={`rounded font-bold flex-shrink-0 ${small ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs'
      } ${active
        ? 'bg-green-900/30 text-green-400 border border-green-800'
        : 'bg-red-900/30 text-red-400 border border-red-800'
      }`}>
      {label}
    </div>
  );
}
