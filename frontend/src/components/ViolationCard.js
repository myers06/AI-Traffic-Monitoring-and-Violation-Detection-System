import { NAMES } from "./StatCards";
import Plate from "./Plate";

export default function ViolationCard({ violation: v, onZoom }) {
  const type = v.type || v.violation_type;
  const riders = v.details?.rider_count;
  const plate = v.plate_number;
  const confidence = v.plate_confidence;
  const [date, time] = (v.timestamp || "").split("T");

  return (
    <article className={`card t-${type}`}>
      <div className="card-media">
        {v.image_url ? (
          <button
            type="button"
            className="media-btn"
            onClick={() => onZoom(v.image_url)}
            aria-label="Enlarge evidence image"
          >
            <img src={v.image_url} alt="Violation evidence" loading="lazy" />
          </button>
        ) : (
          <div className="no-image">No evidence image</div>
        )}
        <span className="type-tag">{NAMES[type] || type}</span>
      </div>

      <div className="card-body">
        <div className="card-plate">
          <Plate text={plate} />
          {plate && confidence != null && (
            <span className="conf">
              {(Number(confidence) * 100).toFixed(0)}% match
            </span>
          )}
        </div>

        <dl className="meta">
          <div>
            <dt>Track</dt>
            <dd>#{v.track_id ?? "–"}</dd>
          </div>
          <div>
            <dt>Frame</dt>
            <dd>{v.frame_idx ?? "–"}</dd>
          </div>
          {riders != null && (
            <div>
              <dt>Riders</dt>
              <dd>{riders}</dd>
            </div>
          )}
          <div>
            <dt>Time</dt>
            <dd title={date}>{time ? time.slice(0, 8) : "–"}</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}
