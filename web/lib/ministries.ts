// Ministry metadata. Codes match crawler/db.py SCHEMA seeds + scripts/assign_ministries.py.

export type MinistryMeta = {
  code: string;
  name_ko: string;
  name_id: string;
  icon: string;        // emoji shortcut
  group: "ekonomi" | "polkam" | "kesra" | "infra" | "lainnya";
};

export const MINISTRIES: MinistryMeta[] = [
  // 경제 (Ekonomi)
  { code: "kemenkeu",        name_ko: "재무부",                name_id: "Kementerian Keuangan",                          icon: "💰", group: "ekonomi" },
  { code: "kemendag",        name_ko: "무역부",                name_id: "Kementerian Perdagangan",                       icon: "🛳", group: "ekonomi" },
  { code: "kemenperin",      name_ko: "산업부",                name_id: "Kementerian Perindustrian",                     icon: "🏭", group: "ekonomi" },
  { code: "kementan",        name_ko: "농업부",                name_id: "Kementerian Pertanian",                         icon: "🌾", group: "ekonomi" },
  { code: "kemenkkp",        name_ko: "해양수산부",            name_id: "Kementerian Kelautan dan Perikanan",            icon: "🐟", group: "ekonomi" },
  { code: "kemenhut",        name_ko: "산림부",                name_id: "Kementerian Kehutanan",                         icon: "🌲", group: "ekonomi" },
  { code: "kemenlh",         name_ko: "환경부",                name_id: "Kementerian Lingkungan Hidup",                  icon: "🌿", group: "ekonomi" },
  { code: "esdm",            name_ko: "에너지광물자원부",      name_id: "Kementerian Energi dan Sumber Daya Mineral",     icon: "⚡", group: "ekonomi" },
  { code: "kemenparekraf",   name_ko: "관광·창조경제부(구)",   name_id: "Kementerian Pariwisata dan Ekonomi Kreatif",     icon: "🏝", group: "ekonomi" },
  { code: "kemenpar",        name_ko: "관광부",                name_id: "Kementerian Pariwisata",                        icon: "🗺", group: "ekonomi" },
  { code: "kemenkopukm",     name_ko: "협동조합·중소기업부",   name_id: "Kementerian Koperasi dan UKM",                  icon: "🤝", group: "ekonomi" },
  { code: "bkpm",            name_ko: "투자조정청",            name_id: "Kementerian Investasi/BKPM",                    icon: "📈", group: "ekonomi" },

  // 국방·안보 (Polkam)
  { code: "kumham",          name_ko: "법무인권부",            name_id: "Kementerian Hukum dan HAM",                     icon: "⚖️", group: "polkam" },
  { code: "kemenhan",        name_ko: "국방부",                name_id: "Kementerian Pertahanan",                        icon: "🛡", group: "polkam" },
  { code: "kemendagri",      name_ko: "내무부",                name_id: "Kementerian Dalam Negeri",                      icon: "🏛", group: "polkam" },
  { code: "kemenlu",         name_ko: "외무부",                name_id: "Kementerian Luar Negeri",                       icon: "🌐", group: "polkam" },
  { code: "kemenimipas",     name_ko: "이민·교정부",           name_id: "Kementerian Imigrasi dan Pemasyarakatan",       icon: "🛂", group: "polkam" },
  { code: "kemensetneg",     name_ko: "국가비서실",            name_id: "Kementerian Sekretariat Negara",                icon: "📜", group: "polkam" },

  // 복지·교육 (Kesra)
  { code: "kemenkes",        name_ko: "보건부",                name_id: "Kementerian Kesehatan",                         icon: "🏥", group: "kesra" },
  { code: "kemenag",         name_ko: "종교부",                name_id: "Kementerian Agama",                             icon: "🕌", group: "kesra" },
  { code: "kemensos",        name_ko: "사회부",                name_id: "Kementerian Sosial",                            icon: "🤲", group: "kesra" },
  { code: "kemenaker",       name_ko: "인력부",                name_id: "Kementerian Ketenagakerjaan",                   icon: "👷", group: "kesra" },
  { code: "kemenpora",       name_ko: "청년체육부",            name_id: "Kementerian Pemuda dan Olahraga",               icon: "⚽", group: "kesra" },
  { code: "kemendikdasmen",  name_ko: "초중등교육부",          name_id: "Kementerian Pendidikan Dasar dan Menengah",      icon: "🎒", group: "kesra" },
  { code: "kemendiktisaintek", name_ko: "고등과학기술부",     name_id: "Kementerian Pendidikan Tinggi, Sains, Teknologi", icon: "🎓", group: "kesra" },
  { code: "kemendikbud",     name_ko: "교육문화부(구)",        name_id: "Kementerian Pendidikan dan Kebudayaan",          icon: "📚", group: "kesra" },
  { code: "kemenkebud",      name_ko: "문화부",                name_id: "Kementerian Kebudayaan",                        icon: "🎭", group: "kesra" },
  { code: "kemenristek",     name_ko: "연구기술부",            name_id: "Kementerian Riset dan Teknologi",                icon: "🔬", group: "kesra" },
  { code: "kemenpppa",       name_ko: "여성·아동권익부",       name_id: "Kementerian PPPA",                              icon: "👶", group: "kesra" },

  // 인프라 (Infra)
  { code: "kemenhub",        name_ko: "교통부",                name_id: "Kementerian Perhubungan",                       icon: "🚢", group: "infra" },
  { code: "kemenpu",         name_ko: "공공사업부",            name_id: "Kementerian Pekerjaan Umum",                    icon: "🚧", group: "infra" },
  { code: "kemenpkp",        name_ko: "주거단지부",            name_id: "Kementerian PKP",                               icon: "🏘", group: "infra" },
  { code: "kemenpera",       name_ko: "주거공급부(구)",        name_id: "Kementerian Perumahan Rakyat",                  icon: "🏠", group: "infra" },
  { code: "atrbpn",          name_ko: "토지·공간행정부",       name_id: "Kementerian ATR/BPN",                           icon: "🗺", group: "infra" },
  { code: "kemenkominfo",    name_ko: "통신정보부(구)",        name_id: "Kementerian Komunikasi dan Informatika",         icon: "📡", group: "infra" },
  { code: "kemenkomdigi",    name_ko: "통신디지털부",          name_id: "Kementerian Komunikasi dan Digital",             icon: "📶", group: "infra" },
  { code: "kemendesa",       name_ko: "마을부",                name_id: "Kementerian Desa, PDT, dan Transmigrasi",        icon: "🏞", group: "infra" },

  // 기타 (Lainnya)
  { code: "kemenpanrb",      name_ko: "행정개혁부",            name_id: "Kementerian PAN-RB",                            icon: "🗂", group: "lainnya" },
  { code: "kemenko",         name_ko: "조정부(전반)",          name_id: "Kementerian Koordinator",                       icon: "🎚", group: "lainnya" },
  { code: "kemenkoinfra",    name_ko: "인프라·지역개발 조정부", name_id: "Kemenko Infrastruktur",                         icon: "🛣", group: "lainnya" },
  { code: "bappenas",        name_ko: "국가개발기획부",        name_id: "Bappenas",                                       icon: "📊", group: "lainnya" },
  { code: "mk",              name_ko: "헌법재판소",            name_id: "Mahkamah Konstitusi",                           icon: "⚜️", group: "lainnya" },
  { code: "ma",              name_ko: "대법원",                name_id: "Mahkamah Agung",                                icon: "🏛️", group: "lainnya" },
];

const BY_CODE: Record<string, MinistryMeta> = MINISTRIES.reduce(
  (acc, m) => ({ ...acc, [m.code]: m }),
  {} as Record<string, MinistryMeta>,
);

export function getMinistry(code: string | null | undefined): MinistryMeta | null {
  if (!code) return null;
  return BY_CODE[code] ?? null;
}

export const GROUP_LABEL: Record<MinistryMeta["group"], string> = {
  ekonomi: "경제·산업",
  polkam:  "정치·법무·외교·국방",
  kesra:   "복지·교육",
  infra:   "인프라·국토",
  lainnya: "기타·조정·사법",
};
