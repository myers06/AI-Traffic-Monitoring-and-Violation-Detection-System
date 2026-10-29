// Renders a number plate the way it looks on the road.
export default function Plate({ text, size = "md" }) {
  if (!text) {
    return <span className={`plate plate-${size} unread`}>Not read</span>;
  }
  return (
    <span className={`plate plate-${size}`}>
      <span className="plate-band" aria-hidden="true" />
      <span className="plate-text">{text}</span>
    </span>
  );
}
