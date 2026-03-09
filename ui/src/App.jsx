import React, { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function fmt(value) {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function apiPost(path, body = null) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

export default function App() {
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [showStart, setShowStart] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filters, setFilters] = useState({ level: "", stage_name: "", service_name: "" });

  const selectedRun = useMemo(() => runs.find((r) => r.id === selectedRunId) || null, [runs, selectedRunId]);

  const loadRuns = async () => {
    try {
      const data = await apiGet("/runs");
      const items = data.items || [];
      setRuns(items);
      setSelectedRunId((prev) => {
        if (prev && items.some((run) => run.id === prev)) {
          return prev;
        }
        if (items.length) {
          return items[0].id;
        }
        return null;
      });
    } catch (e) {
      setError(String(e));
    }
  };

  const loadRun = async (runId) => {
    try {
      const data = await apiGet(`/runs/${runId}`);
      setRunDetail(data);
      const logsData = await apiGet(`/runs/${runId}/logs?limit=200`);
      setLogs(logsData.items || []);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    loadRuns();
    const id = setInterval(loadRuns, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    loadRun(selectedRunId);
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) return;
    const source = new EventSource(`${API_BASE}/runs/${selectedRunId}/events`);
    source.addEventListener("log", (ev) => {
      const item = JSON.parse(ev.data);
      setLogs((prev) => {
        if (prev.some((x) => x.id === item.id)) return prev;
        return [...prev, item].sort((a, b) => a.id - b.id);
      });
    });
    source.addEventListener("run_status", (ev) => {
      const run = JSON.parse(ev.data);
      setRuns((prev) => prev.map((x) => (x.id === run.id ? run : x)));
      setRunDetail((prev) => (prev ? { ...prev, run } : prev));
    });
    source.addEventListener("stage_status", (ev) => {
      const stage = JSON.parse(ev.data);
      setRunDetail((prev) => {
        if (!prev) return prev;
        const stages = (prev.stages || []).filter((x) => x.id !== stage.id).concat(stage).sort((a, b) => a.stage_order - b.stage_order);
        return { ...prev, stages };
      });
    });
    source.addEventListener("progress", (ev) => {
      const progress = JSON.parse(ev.data);
      setRunDetail((prev) => {
        if (!prev) return prev;
        const items = (prev.progress || []).filter((x) => x.stage_name !== progress.stage_name).concat(progress);
        return { ...prev, progress: items };
      });
    });
    source.onerror = () => setError("SSE disconnected, reconnecting...");
    return () => source.close();
  }, [selectedRunId]);

  const activeRun = runs.find((r) => ["pending", "running", "cancelling"].includes(r.status));

  const filteredLogs = logs.filter((log) => {
    if (filters.level && log.level !== filters.level) return false;
    if (filters.stage_name && log.stage_name !== filters.stage_name) return false;
    if (filters.service_name && log.service_name !== filters.service_name) return false;
    return true;
  });

  const submitStartRun = async (formData) => {
    try {
      await apiPost("/runs", formData);
      setShowStart(false);
      loadRuns();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleCommand = async (path, message) => {
    if (!window.confirm(message)) return;
    try {
      await apiPost(path, {});
      loadRuns();
      if (runDetail?.run?.id) {
        loadRun(runDetail.run.id);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="app">
      <header>
        <h1>DocMap Control Plane</h1>
        <div className="header-actions">
          <button onClick={() => setShowStart(true)}>Start Run</button>
          <span className="badge">Active: {activeRun ? `#${activeRun.id} ${activeRun.status}` : "none"}</span>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <main>
        <section className="runs">
          <h2>Runs List</h2>
          {!runs.length ? <div>No pipeline runs yet</div> : null}
          <table>
            <thead>
              <tr>
                <th>Run ID</th><th>Pipeline</th><th>Status</th><th>Current Stage</th><th>Started</th><th>Finished</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className={run.id === selectedRunId ? "selected" : ""} onClick={() => setSelectedRunId(run.id)}>
                  <td>{run.id}</td>
                  <td>{run.pipeline_type}</td>
                  <td>{run.status}</td>
                  <td>{run.current_stage_name || "-"}</td>
                  <td>{fmt(run.started_at)}</td>
                  <td>{fmt(run.finished_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="details">
          <h2>Run Details</h2>
          {!runDetail ? <div>Select a run</div> : (
            <>
              {(() => {
                const detailRunId = runDetail.run.id;
                return (
                  <>
              <div className="card">
                <div>Run ID: {runDetail.run.id}</div>
                <div>Type: {runDetail.run.pipeline_type}</div>
                <div>Status: {runDetail.run.status}</div>
                <div>Current Stage: {runDetail.run.current_stage_name || "-"}</div>
                <div>Target Scope: {runDetail.run.target_scope}</div>
                <div>Started: {fmt(runDetail.run.started_at)}</div>
                <div>Finished: {fmt(runDetail.run.finished_at)}</div>
                {runDetail.run.error_message ? <div>Error: {runDetail.run.error_message}</div> : null}
              </div>

              <div className="actions">
                <button onClick={() => handleCommand(`/runs/${detailRunId}/cancel`, "Cancel this run?")}>Cancel Run</button>
                <button onClick={() => handleCommand(`/runs/${detailRunId}/retry`, "Retry this run as a new run?")}>Retry Run</button>
              </div>

              <h3>Stages</h3>
              <table>
                <thead>
                  <tr>
                    <th>Order</th><th>Stage</th><th>Status</th><th>Done</th><th>Failed</th><th>Started</th><th>Finished</th><th>Retry</th><th>Resume</th>
                  </tr>
                </thead>
                <tbody>
                  {(runDetail.stages || []).map((stage) => (
                    <tr key={stage.id}>
                      <td>{stage.stage_order}</td>
                      <td>{stage.stage_name}</td>
                      <td>{stage.status}</td>
                      <td>{stage.items_completed}</td>
                      <td>{stage.items_failed}</td>
                      <td>{fmt(stage.started_at)}</td>
                      <td>{fmt(stage.finished_at)}</td>
                      <td><button onClick={() => handleCommand(`/runs/${detailRunId}/stages/${stage.stage_name}/retry`, `Retry stage ${stage.stage_name} and downstream?`)}>Retry</button></td>
                      <td><button onClick={() => handleCommand(`/runs/${detailRunId}/stages/${stage.stage_name}/resume`, `Resume stage ${stage.stage_name} from saved progress?`)}>Resume</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h3>Progress</h3>
              {!runDetail.progress?.length ? <div>No progress reported yet</div> : (
                <table>
                  <thead>
                    <tr><th>Stage</th><th>Index</th><th>Total</th><th>Completed</th><th>Failed</th><th>Item</th><th>Message</th><th>Updated</th></tr>
                  </thead>
                  <tbody>
                    {runDetail.progress.map((p) => (
                      <tr key={`${p.stage_name}-${p.updated_at}`}>
                        <td>{p.stage_name}</td>
                        <td>{p.current_index}</td>
                        <td>{p.total_items ?? "-"}</td>
                        <td>{p.items_completed}</td>
                        <td>{p.items_failed}</td>
                        <td>{p.current_document_url ? <a href={p.current_document_url} target="_blank">{p.current_item_label || p.current_document_url}</a> : (p.current_item_label || "-")}</td>
                        <td>{p.message || "-"}</td>
                        <td>{fmt(p.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <h3>Live Logs</h3>
              <div className="filters">
                <input placeholder="level" value={filters.level} onChange={(e) => setFilters({ ...filters, level: e.target.value })} />
                <input placeholder="stage_name" value={filters.stage_name} onChange={(e) => setFilters({ ...filters, stage_name: e.target.value })} />
                <input placeholder="service_name" value={filters.service_name} onChange={(e) => setFilters({ ...filters, service_name: e.target.value })} />
                <label><input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} /> Auto-scroll</label>
              </div>
              <div className="logs" ref={(el) => {
                if (el && autoScroll) {
                  el.scrollTop = el.scrollHeight;
                }
              }}>
                {!filteredLogs.length ? <div>No logs for this run</div> : filteredLogs.map((log) => (
                  <div key={log.id} className="log-line">[{fmt(log.created_at)}] [{log.level}] [{log.service_name}] [{log.stage_name || "-"}] {log.message}</div>
                ))}
              </div>
                  </>
                );
              })()}
            </>
          )}
        </section>
      </main>

      {showStart ? <StartRunModal onClose={() => setShowStart(false)} onSubmit={submitStartRun} /> : null}
    </div>
  );
}

function StartRunModal({ onClose, onSubmit }) {
  const [pipeline_type, setPipelineType] = useState("full_pipeline");
  const [target_scope, setTargetScope] = useState("all");
  const [document_url, setDocumentUrl] = useState("");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");

  const submit = () => {
    const payload = { pipeline_type, target_scope, options: {} };
    if (target_scope === "single_document" && document_url) payload.document_url = document_url;
    if (target_scope === "document_range" && rangeStart && rangeEnd) {
      payload.document_range = { start: Number(rangeStart), end: Number(rangeEnd) };
    }
    onSubmit(payload);
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Start Run</h3>
        <label>Pipeline Type
          <select value={pipeline_type} onChange={(e) => setPipelineType(e.target.value)}>
            <option>full_pipeline</option>
            <option>crawl_only</option>
            <option>extract_only</option>
            <option>geocode_only</option>
            <option>analytics_only</option>
            <option>export_only</option>
          </select>
        </label>
        <label>Target Scope
          <select value={target_scope} onChange={(e) => setTargetScope(e.target.value)}>
            <option>all</option>
            <option>single_document</option>
            <option>document_range</option>
            <option>incremental</option>
          </select>
        </label>
        {target_scope === "single_document" ? <label>Document URL<input value={document_url} onChange={(e) => setDocumentUrl(e.target.value)} /></label> : null}
        {target_scope === "document_range" ? (
          <div className="range-row">
            <label>Start<input value={rangeStart} onChange={(e) => setRangeStart(e.target.value)} /></label>
            <label>End<input value={rangeEnd} onChange={(e) => setRangeEnd(e.target.value)} /></label>
          </div>
        ) : null}
        <div className="actions">
          <button onClick={submit}>Submit</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
