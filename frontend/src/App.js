import { useCallback, useEffect, useState } from "react";
import {
  clearResults,
  getStats,
  getStatus,
  getViolations,
  getDatabaseViolations,
  recognizePhoto,
  startAnalysis,
} from "./api";
import StatCards, { NAMES } from "./components/StatCards";
import Plate from "./components/Plate";
import ViolationCard from "./components/ViolationCard";
import Lightbox from "./components/Lightbox";

const POLL_MS = 2000;

export default function App() {
  const [source, setSource] = useState(
    "videos/17022934_4096_2160_60fps.mp4"
  );
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState({ total: 0, by_type: {} });
  const [rows, setRows] = useState([]);
  const [job, setJob] = useState({
    state: "idle",
    count: 0,
    error: null,
  });
  const [online, setOnline] = useState(true);
  const [zoomed, setZoomed] = useState(null);
  const [notice, setNotice] = useState("");

  // Photo recognition state
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState("");
  const [photoResults, setPhotoResults] = useState(null);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [photoError, setPhotoError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, violations, j, db] = await Promise.all([
        getStats(),
        getViolations(filter),
        getStatus(),
        getDatabaseViolations(),
      ]);

      const mergedRows = violations.map((v) => {
        const record = db.find(
          (d) =>
            String(d.track_id) === String(v.track_id) &&
            d.violation_type === v.type &&
            d.timestamp === v.timestamp
        );

        return {
          ...v,
          plate_number: record?.plate_number ?? null,
          plate_confidence: record?.plate_confidence ?? null,
        };
      });

      setStats(s);
      setRows(mergedRows);
      setJob(j);
      setOnline(true);
    } catch (error) {
      console.error("Dashboard refresh failed:", error);
      setOnline(false);
    }
  }, [filter]);

  useEffect(() => {
    refresh();

    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const handlePhotoRecognition = async () => {
    if (!photo) {
      setPhotoError("Choose a photo first.");
      return;
    }

    setPhotoLoading(true);
    setPhotoError("");
    setPhotoResults(null);

    try {
      const result = await recognizePhoto(photo);
      setPhotoResults(result);
    } catch (error) {
      setPhotoError(error.message || "Photo recognition failed.");
    } finally {
      setPhotoLoading(false);
    }
  };

  const handlePhotoChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setPhotoError("Use a JPG or PNG image.");
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      setPhotoError("This image is over 15 MB. Use a smaller file.");
      return;
    }

    if (photoPreview) {
      URL.revokeObjectURL(photoPreview);
    }

    setPhoto(file);
    setPhotoPreview(URL.createObjectURL(file));
    setPhotoResults(null);
    setPhotoError("");
  };

  useEffect(() => {
    return () => {
      if (photoPreview) {
        URL.revokeObjectURL(photoPreview);
      }
    };
  }, [photoPreview]);

  const run = async () => {
    setNotice("");
    try {
      await startAnalysis(source.trim());
      await refresh();
    } catch (error) {
      setNotice(`Analysis didn't start: ${error.message}`);
    }
  };

  const clear = async () => {
    if (!window.confirm("Delete all saved violations and evidence images?")) {
      return;
    }
    setNotice("");
    try {
      await clearResults();
      await refresh();
    } catch (error) {
      setNotice(`Results weren't cleared: ${error.message}`);
    }
  };

  const running = job.state === "running";

  const statusText = !online
    ? "Server unreachable"
    : job.state === "running"
    ? "Analyzing video"
    : job.state === "done"
    ? `Complete, ${job.count} found`
    : job.state === "error"
    ? `Error: ${job.error}`
    : "Ready";

  const statusClass = !online ? "error" : job.state;
  const filterLabel = filter === "all" ? "All violations" : NAMES[filter];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <i /><i /><i />
          </span>
          <h1>Traffic Violation Monitoring</h1>
        </div>
        <span className={`status ${statusClass}`} role="status">
          <span className="dot" aria-hidden="true" />
          {statusText}
        </span>
      </header>

      <main className="main">
        <section className="runbar" aria-label="Video analysis">
          <label className="field">
            <span>Video file</span>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="videos/your_clip.mp4"
              spellCheck={false}
            />
          </label>
          <div className="runbar-actions">
            <button
              type="button"
              className="btn primary"
              onClick={run}
              disabled={running || !online || !source.trim()}
            >
              {running ? "Analyzing…" : "Run analysis"}
            </button>
            <button
              type="button"
              className="btn ghost"
              onClick={clear}
              disabled={running}
            >
              Clear results
            </button>
          </div>
          {running && <div className="progress" aria-hidden="true" />}
        </section>

        {notice && (
          <div className="notice" role="alert">
            {notice}
            <button type="button" onClick={() => setNotice("")}>
              Dismiss
            </button>
          </div>
        )}

        <StatCards stats={stats} active={filter} onSelect={setFilter} />

        <div className="layout">
          <section className="panel violations">
            <div className="panel-head">
              <h2>{filterLabel}</h2>
              <span className="count">{rows.length}</span>
            </div>

            {rows.length === 0 ? (
              <div className="empty">
                <p className="empty-title">No violations yet</p>
                <p>
                  {filter === "all"
                    ? "Enter a video file above and run an analysis."
                    : `No ${filterLabel.toLowerCase()} violations in the current results.`}
                </p>
              </div>
            ) : (
              <div className="grid">
                {rows.map((v, index) => (
                  <ViolationCard
                    key={`${v.timestamp}-${v.type}-${v.track_id}-${v.frame_idx}-${index}`}
                    violation={v}
                    onZoom={setZoomed}
                  />
                ))}
              </div>
            )}
          </section>

          <aside className="panel photo">
            <div className="panel-head">
              <h2>Read plates from a photo</h2>
            </div>

            <div className="photo-body">
              <label className={`drop${photoPreview ? " has-image" : ""}`}>
                <input
                  type="file"
                  accept="image/jpeg,image/png"
                  onChange={handlePhotoChange}
                />
                {photoPreview ? (
                  <img src={photoPreview} alt="Selected traffic" />
                ) : (
                  <span className="drop-hint">
                    <strong>Choose a photo</strong>
                    JPG or PNG, up to 15 MB
                  </span>
                )}
              </label>

              {photo && (
                <p className="file-name" title={photo.name}>
                  {photo.name}
                </p>
              )}

              <button
                type="button"
                className="btn primary block"
                onClick={handlePhotoRecognition}
                disabled={!photo || photoLoading}
              >
                {photoLoading ? "Reading plates…" : "Read plates"}
              </button>

              {photoError && (
                <p className="error-text" role="alert">
                  {photoError}
                </p>
              )}

              {photoResults && (
                <div className="results">
                  <p className="results-head">
                    {photoResults.plate_count === 1
                      ? "1 plate found"
                      : `${photoResults.plate_count} plates found`}
                  </p>
                  {photoResults.message && (
                    <p className="results-msg">{photoResults.message}</p>
                  )}

                  <ul>
                    {photoResults.plates.map((plate, index) => (
                      <li key={`${plate.text || "unknown"}-${index}`}>
                        <Plate text={plate.text} size="sm" />
                        <span className="conf">
                          {(plate.detection_confidence * 100).toFixed(0)}%
                        </span>
                        <span
                          className="coords"
                          title="Plate position in the photo (x1, y1) to (x2, y2)"
                        >
                          {plate.box.x1},{plate.box.y1} – {plate.box.x2},
                          {plate.box.y2}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </aside>
        </div>
      </main>

      <Lightbox src={zoomed} onClose={() => setZoomed(null)} />
    </div>
  );
}
