export const TYPES = ["triple_riding", "no_helmet", "red_light"];
export const NAMES = {
  triple_riding: "Triple riding",
  no_helmet: "No helmet",
  red_light: "Red light",
};

// Clicking a count filters the violations list.
export default function StatCards({ stats, active, onSelect }) {
  const items = [
    ["all", "All violations", stats.total],
    ...TYPES.map((t) => [t, NAMES[t], stats.by_type[t] || 0]),
  ];

  return (
    <nav className="stats" aria-label="Filter by violation type">
      {items.map(([key, label, n]) => (
        <button
          key={key}
          type="button"
          className={`stat t-${key}${active === key ? " active" : ""}`}
          aria-pressed={active === key}
          onClick={() => onSelect(key)}
        >
          <span className="n">{n}</span>
          <span className="l">{label}</span>
        </button>
      ))}
    </nav>
  );
}
