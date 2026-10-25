import { NAMES } from "./StatCards";

export default function ViolationCard({ violation: v, onZoom }) {
  const riders = v.details?.rider_count;
  return (
    <div className="card">
      {v.image_url ? (
        <img
          src={v.image_url}
          alt="Violation evidence"
          loading="lazy"
          onClick={() => onZoom(v.image_url)}
        />
      ) : (
        <div className="no-image">No image</div>
      )}
      <div className="body">
        <div className="badge">{NAMES[v.type] || v.type}</div>
        <Row label="Track ID" value={`#${v.track_id}`} />
        <Row label="Frame" value={v.frame_idx} />
        {riders != null && <Row label="Riders" value={riders} />}
        <Row label="Time" value={(v.timestamp || "").replace("T", " ")} />
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="row">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}