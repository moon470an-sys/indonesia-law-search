import { classify, getHierarchy } from "@/lib/hierarchy";

type Props = {
  law: { law_type: string; category?: string | null; source_url?: string | null };
  size?: "sm" | "md" | "lg";
  showId?: boolean;       // show Indonesian short tag like "UU"
};

export default function HierarchyBadge({ law, size = "sm", showId = false }: Props) {
  const key = classify(law);
  const h = getHierarchy(key);
  const padding =
    size === "lg" ? "px-3 py-1.5 text-sm" :
    size === "md" ? "px-2.5 py-1 text-xs" :
    "px-2 py-0.5 text-[11px]";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-bold ring-1 whitespace-nowrap ${h.classes.badge} ${padding}`}
    >
      {h.name_ko}
      {showId && (
        <span className="font-semibold opacity-70">· {h.key.replace("_", " ")}</span>
      )}
    </span>
  );
}
