from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = FastAPI(title="File Archive API")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "archivedb"),
    "user": os.getenv("DB_USER", "archiveuser"),
    "password": os.getenv("DB_PASSWORD", "archivepass"),
}


def get_db():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


@app.get("/runs")
def get_runs():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, group_name, started_at, finished_at,
                   duration, total_moved, total_skipped, total_errors, status
            FROM archive_runs ORDER BY started_at DESC
        """)
        runs = cur.fetchall()
    conn.close()
    return [dict(r) for r in runs]


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, group_name, started_at, finished_at,
                   duration, total_moved, total_skipped, total_errors, status
            FROM archive_runs WHERE id = %s
        """, (run_id,))
        run = cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        cur.execute("""
            SELECT source, destination, status, reason, timestamp
            FROM archive_events WHERE run_id = %s ORDER BY timestamp
        """, (run_id,))
        files = cur.fetchall()
    conn.close()
    result = dict(run)
    result["files"] = [dict(f) for f in files]
    return result


@app.get("/runs/{run_id}/files")
def get_run_files(run_id: int, status: str = Query(None)):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM archive_runs WHERE id = %s", (run_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        if status:
            cur.execute("""
                SELECT source, destination, status, reason, timestamp
                FROM archive_events WHERE run_id = %s AND status = %s ORDER BY timestamp
            """, (run_id, status))
        else:
            cur.execute("""
                SELECT source, destination, status, reason, timestamp
                FROM archive_events WHERE run_id = %s ORDER BY timestamp
            """, (run_id,))
        files = cur.fetchall()
    conn.close()
    return [dict(f) for f in files]


@app.get("/stats")
def get_stats():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*)                          AS total_runs,
                COALESCE(SUM(total_moved), 0)     AS total_files_archived,
                COALESCE(SUM(total_skipped), 0)   AS total_skipped,
                COALESCE(SUM(total_errors), 0)    AS total_errors,
                (SELECT group_name FROM archive_runs ORDER BY started_at DESC LIMIT 1)
                                                  AS most_recent_group,
                (SELECT group_name FROM archive_runs
                 GROUP BY group_name ORDER BY SUM(total_moved) DESC LIMIT 1)
                                                  AS busiest_group
            FROM archive_runs
        """)
        stats = cur.fetchone()
    conn.close()
    return dict(stats)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Archive Dashboard</title>
  <style>
    body { font-family: sans-serif; margin: 2rem; background: #f5f5f5; }
    h1 { color: #333; }
    .summary { display: flex; gap: 1rem; margin-bottom: 2rem; }
    .card { background: white; padding: 1rem 2rem; border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1); text-align: center; }
    .card h2 { margin: 0; font-size: 2rem; color: #2563eb; }
    .card p  { margin: 0; color: #666; font-size: 0.9rem; }
    table { width: 100%; border-collapse: collapse; background: white;
            border-radius: 8px; overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
    th { background: #2563eb; color: white; padding: 0.75rem 1rem; text-align: left; }
    td { padding: 0.75rem 1rem; border-bottom: 1px solid #eee; cursor: pointer; }
    tr:hover td { background: #eff6ff; }
    .status-completed { color: green; font-weight: bold; }
    .status-completed_with_errors { color: orange; font-weight: bold; }
    .status-running { color: blue; font-weight: bold; }
    #detail { margin-top: 2rem; display: none; }
    #detail h2 { color: #333; }
    .moved { color: green; } .skipped { color: gray; } .error { color: red; }
  </style>
</head>
<body>
  <h1>📁 File Archive Dashboard</h1>

  <div class="summary">
    <div class="card"><h2 id="s-runs">—</h2><p>Total Runs</p></div>
    <div class="card"><h2 id="s-archived">—</h2><p>Files Archived</p></div>
    <div class="card"><h2 id="s-skipped">—</h2><p>Skipped</p></div>
    <div class="card"><h2 id="s-errors">—</h2><p>Errors</p></div>
  </div>

  <table id="runs-table">
    <thead>
      <tr>
        <th>ID</th><th>Group</th><th>Started At</th><th>Duration (s)</th>
        <th>Moved</th><th>Skipped</th><th>Errors</th><th>Status</th>
      </tr>
    </thead>
    <tbody id="runs-body"></tbody>
  </table>

  <div id="detail">
    <h2 id="detail-title">Run Detail</h2>
    <table>
      <thead>
        <tr><th>Source</th><th>Destination</th><th>Status</th><th>Reason</th><th>Timestamp</th></tr>
      </thead>
      <tbody id="detail-body"></tbody>
    </table>
  </div>

<script>
  async function loadStats() {
    const r = await fetch('/stats');
    const s = await r.json();
    document.getElementById('s-runs').textContent     = s.total_runs     ?? 0;
    document.getElementById('s-archived').textContent = s.total_files_archived ?? 0;
    document.getElementById('s-skipped').textContent  = s.total_skipped  ?? 0;
    document.getElementById('s-errors').textContent   = s.total_errors   ?? 0;
  }

  async function loadRuns() {
    const r = await fetch('/runs');
    const runs = await r.json();
    const tbody = document.getElementById('runs-body');
    tbody.innerHTML = '';
    runs.forEach(run => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${run.id}</td>
        <td>${run.group_name}</td>
        <td>${new Date(run.started_at).toLocaleString()}</td>
        <td>${run.duration != null ? run.duration.toFixed(2) : '—'}</td>
        <td>${run.total_moved}</td>
        <td>${run.total_skipped}</td>
        <td>${run.total_errors}</td>
        <td class="status-${run.status}">${run.status}</td>
      `;
      tr.onclick = () => loadDetail(run.id, run.group_name);
      tbody.appendChild(tr);
    });
  }

  async function loadDetail(runId, groupName) {
    const r = await fetch(`/runs/${runId}`);
    const run = await r.json();
    document.getElementById('detail-title').textContent = `Run #${runId} — ${groupName}`;
    const tbody = document.getElementById('detail-body');
    tbody.innerHTML = '';
    run.files.forEach(f => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${f.source}</td>
        <td>${f.destination}</td>
        <td class="${f.status}">${f.status}</td>
        <td>${f.reason ?? ''}</td>
        <td>${new Date(f.timestamp).toLocaleString()}</td>
      `;
      tbody.appendChild(tr);
    });
    document.getElementById('detail').style.display = 'block';
  }

  function refresh() { loadStats(); loadRuns(); }
  refresh();
  setInterval(refresh, 10000);
</script>
</body>
</html>
"""