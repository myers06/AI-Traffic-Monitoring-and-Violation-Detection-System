export const TYPES = ["triple_riding", "no_helmet", "red_light"];
export const NAMES = {
  triple_riding: "Triple Riding",
  no_helmet: "No Helmet",
  red_light: "Red Light",
};

export default function StatCards({ stats }) {
  const items = [
    ["Total Violations", stats.total],
    ...TYPES.map((t) => [NAMES[t], stats.by_type[t] || 0]),
  ];
  return (
    <div className="stats">
      {items.map(([label, n]) => (
        <div className="stat" key={label}>
          <div className="l">{label}</div>
          <div className="n">{n}</div>
        </div>
      ))}
    </div>
  );
}