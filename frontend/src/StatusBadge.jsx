const STATUS_STYLES = {
  accepted: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  duplicate: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  conflict: "bg-red-500/20 text-red-300 border-red-500/40",
};

const DEFAULT_STYLE = "bg-slate-500/20 text-slate-300 border-slate-500/40";

export default function StatusBadge({ status }) {
  const cls = STATUS_STYLES[status] || DEFAULT_STYLE;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {status}
    </span>
  );
}
