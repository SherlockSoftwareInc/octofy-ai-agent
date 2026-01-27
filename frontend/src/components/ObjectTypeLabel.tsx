type ObjectTypeLabelProps = {
  type?: string | null;
};

const typeStyles: Record<string, string> = {
  table: "bg-blue-500/20 text-blue-300",
  view: "bg-purple-500/20 text-purple-300",
};

export function ObjectTypeLabel({ type }: ObjectTypeLabelProps) {
  const normalizedType = type ? type.trim().toLowerCase() : "";
  const label = normalizedType && typeStyles[normalizedType] ? normalizedType : "other";
  const colorClass = typeStyles[label] || "bg-slate-500/20 text-slate-300";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-xs ${colorClass}`}
    >
      {label}
    </span>
  );
}
