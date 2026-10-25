import { useCallback, useEffect, useState } from "react";
import {
  clearResults,
  getStats,
  getStatus,
  getViolations,
  startAnalysis,
} from "./api";
import StatCards from "./components/StatCards";
import Filters from "./components/Filters";
import ViolationCard from "./components/ViolationCard";
import Lightbox from "./components/Lightbox";

const POLL_MS = 2000;

export default function App() {
  const [source, setSource] = useState("data/input/test.mp4");
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState({ total: 0, by_type: {} });
  const [rows, setRows] = useState([]);
  const [job, setJob] = useState({ state: "idle", count: 0, error: null });
  const [online, setOnline] = useState(true);
  const [zoomed, setZoomed] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r, j] = await Promise.all([
        getStats(),
        getViolations(filter),
        getStatus(),
      ]);
      setStats(s);
      setRows(r);
      setJob(j);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, [filter]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const run = async () => {
    try {
      await startAnalysis(source.trim());
      refresh();
    } catch (e) {
      alert(e.message);
    }
  };

  const clear = async () => {
    if (!window.confirm("Delete all saved violations and evidence images?")) return;
    try {
      await clearResults();
      refresh();
    } catch (e) {
      alert(e.message);
    }
  };

  const running = job.state === "running";
  const statusText = !online
    ? "SERVER UNREACHABLE"
    : job.state === "done"
    ? `COMPLETE · ${job.count} FOUND`
    : job.state === "error"
    ? `ERROR: ${job.error}`
    : job.state.toUpperCase();
  const statusClass = !online ? "error" : job.state;

  return (
    <>
      <header className="header">
        <h1>Traffic Violation Monitoring</h1>
        <div className="controls">
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Video path"
          />
          <button className="primary" onClick={run} disabled={running || !online}>
            {running ? "Running..." : "Run analysis"}
          </button>
          <button className="secondary" onClick={clear} disabled={running}>
            Clear results
          </button>
          <span className={`status ${statusClass}`}>{statusText}</span>
        </div>
      </header>

      <main className="main">
        <StatCards stats={stats} />

        <section className="panel">
          <div className="panel-head">
            <h2>Detected Violations</h2>
            <Filters value={filter} onChange={setFilter} />
          </div>

          {rows.length === 0 ? (
            <div className="empty">
              No violations recorded. Run an analysis to begin.
            </div>
          ) : (
            <div className="grid">
              {rows.map((v) => (
                <ViolationCard
                  key={`${v.timestamp}-${v.type}-${v.track_id}-${v.frame_idx}`}
                  violation={v}
                  onZoom={setZoomed}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      <Lightbox src={zoomed} onClose={() => setZoomed(null)} />
    </>
  );
}