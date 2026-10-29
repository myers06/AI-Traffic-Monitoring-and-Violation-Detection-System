import { useCallback, useEffect, useRef, useState } from "react";
import {
  clearResults,
  getDatabaseViolations,
  getPlates,
  getStats,
  getStatus,
  getVideos,
  getViolations,
  recognizePhoto,
  startAnalysis,
  uploadVideo,
  videoUrl,
} from "./api";
import StatCards, { NAMES } from "./components/StatCards";
import Plate from "./components/Plate";
import PlateList from "./components/PlateList";
import ViolationCard from "./components/ViolationCard";
import Lightbox from "./components/Lightbox";

const POLL_MS = 2000;
const VIDEO_TYPES = ".mp4,.mov,.avi,.mkv,.webm,.m4v";

// "2026-10-29 10:14:22.512" / "2026-10-29T10:14:22" -> ms
const toMs = (t) => (t ? new Date(String(t).trim().replace(" ", "T")).getTime() : NaN);

export default function App() {
  // videos
  const [videos, setVideos] = useState([]);
  const [source, setSource] = useState("");
  const [upload, setUpload] = useState(null); // { name, pct }
  const [showPlayer, setShowPlayer] = useState(false);
  const playerRef = useRef(null);

  // results
  const [filter, setFilter] = useState("all");
  const [stats, setStats] = useState({ total: 0, by_type: {} });
  const [rows, setRows] = useState([]);
  const [plates, setPlates] = useState([]);
  const [job, setJob] = useState({ state: "idle", count: 0, progress: 0, error: null });
  const [online, setOnline] = useState(true);
  const [zoomed, setZoomed] = useState(null);
  const [notice, setNotice] = useState("");

  // photo recognition
  const [photo, setPhoto] = useState(null);
  const [photoPreview, setPhotoPreview] = useState("");
  const [photoResults, setPhotoResults] = useState(null);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [photoError, setPhotoError] = useState("");

  const loadVideos = useCallback(async (select) => {
    try {
      const list = await getVideos();
      setVideos(list);
      setSource((cur) => select || cur || list[0]?.path || "");
    } catch (error) {
      console.error("Could not load videos:", error);
    }
  }, []);

  useEffect(() => {
    loadVideos();
  }, [loadVideos]);

  const refresh = useCallback(async () => {
    try {
      const [s, violations, j, db, p] = await Promise.all([
        getStats(),
        getViolations(filter),
        getStatus(),
        getDatabaseViolations(),
        source ? getPlates(source) : Promise.resolve([]),
      ]);

      const merged = violations.map((v) => {
        const vType = v.type || v.violation_type;
        const vTime = toMs(v.timestamp);
        let record = null;
        let best = Infinity;
        for (const d of db) {
          if (
            String(d.track_id) !== String(v.track_id) ||
            (d.violation_type || d.type) !== vType ||
            !d.plate_number
          ) {
            continue;
          }
          const diff = Math.abs(toMs(d.timestamp) - vTime);
          const score = Number.isNaN(diff) ? 1e12 : diff;
          if (score < best) {
            best = score;
            record = d;
          }
        }
        return {
          ...v,
          plate_number: record?.plate_number ?? null,
          plate_confidence: record?.plate_confidence ?? null,
        };
      });

      setStats(s);
      setRows(merged);
      setJob(j);
      setPlates(p);
      setOnline(true);
    } catch (error) {
      console.error("Dashboard refresh failed:", error);
      setOnline(false);
    }
  }, [filter, source]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // -- video actions ---------------------------------------------------------
  const run = async () => {
    setNotice("");
    try {
      await startAnalysis(source);
      await refresh();
    } catch (error) {
      setNotice(`Analysis didn't start: ${error.message}`);
    }
  };

  const handleVideoUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow picking the same file again
    if (!file) return;

    setNotice("");
    setUpload({ name: file.name, pct: 0 });
    try {
      const res = await uploadVideo(file, (pct) =>
        setUpload({ name: file.name, pct })
      );
      await loadVideos(res.path);
      setSource(res.path);
      await refresh();
    } catch (error) {
      setNotice(`Upload failed: ${error.message}`);
    } finally {
      setUpload(null);
    }
  };

  const clear = async () => {
    if (!window.confirm("Delete all saved violations, plates and evidence images?")) {
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

  const seek = (sec) => {
    setShowPlayer(true);
    // wait for the player to mount before seeking
    setTimeout(() => {
      const v = playerRef.current;
      if (!v) return;
      v.currentTime = Math.max(0, (sec || 0) - 0.5);
      v.play().catch(() => {});
    }, 50);
  };

  // -- photo actions ---------------------------------------------------------
  const handlePhotoRecognition = async () => {
    if (!photo) {
      setPhotoError("Choose a photo first.");
      return;
    }
    setPhotoLoading(true);
    setPhotoError("");
    setPhotoResults(null);
    try {
      setPhotoResults(await recognizePhoto(photo));
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
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhoto(file);
    setPhotoPreview(URL.createObjectURL(file));
    setPhotoResults(null);
    setPhotoError("");
  };

  useEffect(() => {
    return () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview);
    };
  }, [photoPreview]);

  // -- derived ---------------------------------------------------------------
  const running = job.state === "running";
  const uploading = upload !== null;
  const busy = running || uploading;
  const runningThis = running && job.video === source;

  const statusText = !online
    ? "Server unreachable"
    : uploading
    ? `Uploading, ${upload.pct}%`
    : running
    ? `Analyzing, ${job.progress ?? 0}%`
    : job.state === "done"
    ? `Complete, ${job.count} violation${job.count === 1 ? "" : "s"}`
    : job.state === "error"
    ? `Error: ${job.error}`
    : "Ready";

  const statusClass = !online ? "error" : uploading ? "running" : job.state;
  const filterLabel = filter === "all" ? "All violations" : NAMES[filter];
  const barPct = uploading ? upload.pct : running ? job.progress ?? 0 : null;

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
            <span>Video</span>
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setShowPlayer(false);
              }}
              disabled={uploading}
            >
              {videos.length === 0 && <option value="">No videos yet. Upload one.</option>}
              {videos.map((v) => (
                <option key={v.path} value={v.path}>
                  {v.name} ({v.size_mb} MB){v.uploaded ? ", uploaded" : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="runbar-actions">
            <label className={`btn ghost upload-btn${busy ? " disabled" : ""}`}>
              <input
                type="file"
                accept={VIDEO_TYPES}
                onChange={handleVideoUpload}
                disabled={busy || !online}
              />
              Upload video
            </label>
            <button
              type="button"
              className="btn primary"
              onClick={run}
              disabled={busy || !online || !source}
            >
              {running ? "Analyzing…" : "Run analysis"}
            </button>
            <button
              type="button"
              className="btn ghost danger"
              onClick={clear}
              disabled={busy}
            >
              Clear results
            </button>
          </div>

          {barPct !== null && (
            <div className="progress" aria-hidden="true">
              <div className="progress-fill" style={{ width: `${barPct}%` }} />
            </div>
          )}
          {uploading && (
            <p className="upload-note">
              Uploading {upload.name}. Analysis starts when the upload finishes.
            </p>
          )}
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
          <div className="stack">
            <section className="panel">
              <div className="panel-head">
                <h2>Plates in this video</h2>
                <span className="count">{plates.length}</span>
                {source && (
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => setShowPlayer((s) => !s)}
                  >
                    {showPlayer ? "Hide video" : "Play video"}
                  </button>
                )}
              </div>

              {showPlayer && source && (
                <video
                  ref={playerRef}
                  className="player"
                  src={videoUrl(source)}
                  controls
                  preload="metadata"
                />
              )}

              {plates.length === 0 ? (
                <div className="empty">
                  <p className="empty-title">
                    {runningThis ? "Reading plates…" : "No plates read yet"}
                  </p>
                  <p>
                    {runningThis
                      ? "Plates appear here as each vehicle leaves the frame."
                      : "Run an analysis on this video, or upload a new one."}
                  </p>
                </div>
              ) : (
                <PlateList plates={plates} onSeek={seek} />
              )}
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>{filterLabel}</h2>
                <span className="count">{rows.length}</span>
              </div>

              {rows.length === 0 ? (
                <div className="empty">
                  <p className="empty-title">No violations yet</p>
                  <p>
                    {filter === "all"
                      ? "Violations from analyzed videos show up here."
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
          </div>

          <aside className="panel photo">
            <div className="panel-head">
              <h2>Read plates from a photo</h2>
            </div>

            <div className="photo-body">
              <label className={`drop${photoPreview ? " has-image" : ""}`}>
                <input type="file" accept="image/jpeg,image/png" onChange={handlePhotoChange} />
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
                  {photoResults.message && <p className="results-msg">{photoResults.message}</p>}
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
                          {plate.box.x1},{plate.box.y1} – {plate.box.x2},{plate.box.y2}
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
