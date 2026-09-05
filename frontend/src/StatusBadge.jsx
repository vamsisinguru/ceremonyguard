const STATUS_STYLES = {
  accepted: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  duplicate: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  conflict: "bg-red-500/20 text-red-300 border-red-500/40",
  ready: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  incomplete: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  recovering: "bg-sky-500/20 text-sky-300 border-sky-500/40",
  verified: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  verification_failed: "bg-red-500/20 text-red-300 border-red-500/40",
  not_generated: "bg-slate-500/20 text-slate-300 border-slate-500/40",
  not_ready: "bg-amber-500/20 text-amber-300 border-amber-500/40",
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
