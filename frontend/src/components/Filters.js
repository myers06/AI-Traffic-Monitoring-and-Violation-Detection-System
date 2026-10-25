import { NAMES, TYPES } from "./StatCards";

export default function Filters({ value, onChange }) {
  const options = [["all", "All"], ...TYPES.map((t) => [t, NAMES[t]])];
  return (
    <div className="filters">
      {options.map(([v, label]) => (
        <button
          key={v}
          className={value === v ? "active" : ""}
          onClick={() => onChange(v)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}