// 인도네시아 법위계 (Hierarki Peraturan Perundang-undangan, UU 12/2011 + 행정규칙)
//
// 데이터 모델: 한 법령(law)을 정확히 한 hierarchy bucket으로 매핑한다.
// law_type 필드가 다양한 표기로 존재하므로 (Permenkeu / Permenhut / "KEPUTUSAN MENTERI ESDM" 등)
// classify() 가 정규화한다.

export type HierarchyKey =
  | "UUD"       // 헌법 (1945)
  | "TAP"       // TAP MPR (인민협의회 결의)
  | "UU"        // 법률 (Perppu 포함)
  | "PP"        // 정부령 (시행령)
  | "Perpres"   // 대통령령
  | "Permen"    // 부령 (Permen + 모든 Permen<X>)
  | "Kepmen"    // 장관 결정
  | "Perda_Prov"// 도 조례
  | "Perda_Kab" // 시·군 조례
  | "Lainnya";  // 기타

export type Hierarchy = {
  key: HierarchyKey;
  name_ko: string;
  name_id: string;
  rank: number;        // 1 = 최상위
  /** Tailwind 색상 토큰 — 정적이어야 PurgeCSS가 잡음 */
  classes: {
    text: string;       // 강조 텍스트
    bg: string;         // 약한 배경
    bgStrong: string;   // 진한 배경 (헤더용)
    border: string;     // 좌측 강조 막대
    badge: string;      // 배지 (bg + text 합쳐서)
    ring: string;       // hover 링
  };
};

export const HIERARCHIES: Hierarchy[] = [
  {
    key: "UUD", name_ko: "헌법", name_id: "Undang-Undang Dasar 1945", rank: 1,
    classes: {
      text:      "text-violet-700",
      bg:        "bg-violet-50",
      bgStrong:  "bg-violet-700",
      border:    "border-violet-500",
      badge:     "bg-violet-100 text-violet-800 ring-violet-200",
      ring:      "hover:ring-violet-300",
    },
  },
  {
    key: "TAP", name_ko: "MPR 결의", name_id: "Ketetapan MPR", rank: 2,
    classes: {
      text:      "text-fuchsia-700",
      bg:        "bg-fuchsia-50",
      bgStrong:  "bg-fuchsia-700",
      border:    "border-fuchsia-500",
      badge:     "bg-fuchsia-100 text-fuchsia-800 ring-fuchsia-200",
      ring:      "hover:ring-fuchsia-300",
    },
  },
  {
    key: "UU", name_ko: "법률", name_id: "Undang-Undang (UU)", rank: 3,
    classes: {
      text:      "text-indigo-700",
      bg:        "bg-indigo-50",
      bgStrong:  "bg-indigo-700",
      border:    "border-indigo-500",
      badge:     "bg-indigo-100 text-indigo-800 ring-indigo-200",
      ring:      "hover:ring-indigo-300",
    },
  },
  {
    key: "PP", name_ko: "정부령", name_id: "Peraturan Pemerintah (PP)", rank: 4,
    classes: {
      text:      "text-blue-700",
      bg:        "bg-blue-50",
      bgStrong:  "bg-blue-700",
      border:    "border-blue-500",
      badge:     "bg-blue-100 text-blue-800 ring-blue-200",
      ring:      "hover:ring-blue-300",
    },
  },
  {
    key: "Perpres", name_ko: "대통령령", name_id: "Peraturan Presiden (Perpres)", rank: 5,
    classes: {
      text:      "text-sky-700",
      bg:        "bg-sky-50",
      bgStrong:  "bg-sky-700",
      border:    "border-sky-500",
      badge:     "bg-sky-100 text-sky-800 ring-sky-200",
      ring:      "hover:ring-sky-300",
    },
  },
  {
    key: "Permen", name_ko: "부령", name_id: "Peraturan Menteri (Permen)", rank: 6,
    classes: {
      text:      "text-teal-700",
      bg:        "bg-teal-50",
      bgStrong:  "bg-teal-700",
      border:    "border-teal-500",
      badge:     "bg-teal-100 text-teal-800 ring-teal-200",
      ring:      "hover:ring-teal-300",
    },
  },
  {
    key: "Kepmen", name_ko: "장관결정", name_id: "Keputusan Menteri (Kepmen)", rank: 7,
    classes: {
      text:      "text-emerald-700",
      bg:        "bg-emerald-50",
      bgStrong:  "bg-emerald-700",
      border:    "border-emerald-500",
      badge:     "bg-emerald-100 text-emerald-800 ring-emerald-200",
      ring:      "hover:ring-emerald-300",
    },
  },
  {
    key: "Perda_Prov", name_ko: "도 조례", name_id: "Peraturan Daerah Provinsi", rank: 8,
    classes: {
      text:      "text-amber-700",
      bg:        "bg-amber-50",
      bgStrong:  "bg-amber-600",
      border:    "border-amber-500",
      badge:     "bg-amber-100 text-amber-800 ring-amber-200",
      ring:      "hover:ring-amber-300",
    },
  },
  {
    key: "Perda_Kab", name_ko: "시·군 조례", name_id: "Peraturan Daerah Kabupaten/Kota", rank: 9,
    classes: {
      text:      "text-orange-700",
      bg:        "bg-orange-50",
      bgStrong:  "bg-orange-600",
      border:    "border-orange-500",
      badge:     "bg-orange-100 text-orange-800 ring-orange-200",
      ring:      "hover:ring-orange-300",
    },
  },
  {
    key: "Lainnya", name_ko: "기타", name_id: "Lainnya", rank: 99,
    classes: {
      text:      "text-slate-700",
      bg:        "bg-slate-100",
      bgStrong:  "bg-slate-600",
      border:    "border-slate-400",
      badge:     "bg-slate-100 text-slate-700 ring-slate-200",
      ring:      "hover:ring-slate-300",
    },
  },
];

const BY_KEY: Record<HierarchyKey, Hierarchy> = HIERARCHIES.reduce(
  (acc, h) => ({ ...acc, [h.key]: h }),
  {} as Record<HierarchyKey, Hierarchy>,
);

/**
 * Normalize the wide variety of law_type strings into a hierarchy key.
 * Source field can be: "UU" | "PP" | "Perpres" | "Permen" | "Permenkeu" |
 *   "Permendag" | "KEPUTUSAN MENTERI ESDM" | "Perda" | "Perwako" | "Pergub" | …
 */
export function classify(input: {
  law_type: string;
  category?: string | null;
  source_url?: string | null;
}): HierarchyKey {
  const lt = (input.law_type || "").trim().toLowerCase();
  const cat = (input.category || "").toLowerCase();
  const url = (input.source_url || "").toLowerCase();

  if (cat === "putusan") return "Lainnya"; // 판례는 별도 trail이지만 위계 모드에서는 lainnya
  if (cat === "lampiran" || cat === "perjanjian" || cat === "lainnya") return "Lainnya";

  if (lt === "uud" || lt === "uud 1945") return "UUD";
  if (lt === "tap" || lt.startsWith("tap mpr")) return "TAP";
  if (lt === "uu" || lt === "perppu" || lt.startsWith("uu ") || lt === "undang-undang") return "UU";
  if (lt === "pp" || lt === "peraturan pemerintah") return "PP";
  if (lt === "perpres" || lt === "peraturan presiden") return "Perpres";

  // Permen 패밀리: Permen, Permenkeu, Permendag, Permenhut, Permenkumham, …
  if (lt === "permen" || lt.startsWith("permen") || lt.startsWith("peraturan menteri")) {
    return "Permen";
  }

  // Kepmen 패밀리: 'KEPUTUSAN MENTERI ESDM', 'Kepmen', …
  if (lt === "kepmen" || lt.includes("keputusan menteri") || lt.startsWith("keputusan ")) {
    return "Kepmen";
  }

  // 지방법규 — slug에서 도/시군 구분
  if (
    lt === "perda" || lt.startsWith("pergub") || lt.startsWith("perwako") ||
    lt.startsWith("perwali") || lt.startsWith("perbup") ||
    lt.startsWith("peraturan daerah") || cat === "perda"
  ) {
    if (url.includes("provinsi") || lt.startsWith("pergub") || lt.includes("provinsi")) {
      return "Perda_Prov";
    }
    return "Perda_Kab";
  }

  return "Lainnya";
}

export function getHierarchy(key: HierarchyKey): Hierarchy {
  return BY_KEY[key] ?? BY_KEY["Lainnya"];
}

/** Sort helper: by hierarchy rank then by promulgation_date desc */
export function compareByHierarchy<T extends { law_type: string; category?: string | null; source_url?: string | null; promulgation_date?: string | null }>(a: T, b: T): number {
  const ra = getHierarchy(classify(a)).rank;
  const rb = getHierarchy(classify(b)).rank;
  if (ra !== rb) return ra - rb;
  return (b.promulgation_date ?? "").localeCompare(a.promulgation_date ?? "");
}
