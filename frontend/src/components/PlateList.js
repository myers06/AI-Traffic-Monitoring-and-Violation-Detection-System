import Plate from "./Plate";

const VEHICLE = { car: "Car", motorcycle: "Motorcycle", bus: "Bus", truck: "Truck" };

export const fmtTime = (sec) => {
  const s = Math.max(0, Math.floor(sec || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export default function PlateList({ plates, onSeek }) {
  return (
    <ul className="plate-list">
      {plates.map((p) => (
        <li key={p.id}>
          <button
            type="button"
            className="plate-row"
            onClick={() => onSeek(p.first_seen_sec)}
            title="Jump to this moment in the video"
          >
            <span className="plate-thumb">
              {p.image_url ? (
                <img src={p.image_url} alt={`Plate ${p.plate_number}`} loading="lazy" />
              ) : null}
            </span>
            <span className="plate-info">
              <Plate text={p.plate_number} size="sm" />
              <span className="plate-meta">
                {VEHICLE[p.vehicle] || p.vehicle || "Vehicle"}
                {", "}
                {fmtTime(p.first_seen_sec)}
                {p.last_seen_sec > p.first_seen_sec
                  ? `–${fmtTime(p.last_seen_sec)}`
                  : ""}
              </span>
            </span>
            <span className="conf">
              {Math.round((p.plate_confidence || 0) * 100)}%
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
