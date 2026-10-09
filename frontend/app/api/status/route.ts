export const dynamic = 'force-dynamic';
export async function GET() {
  try {
    const response = await fetch(`${process.env.MONITOR_API_URL || 'http://monitor-backend:8000'}/status`, {
      cache: 'no-store', signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error('Backend unavailable');
    return Response.json(await response.json(), { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'Monitor is unavailable. Try refreshing shortly.' }, { status: 502 });
  }
}
