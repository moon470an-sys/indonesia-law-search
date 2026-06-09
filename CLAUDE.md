# 인도네시아 법령 프로젝트 - Claude Code 컨텍스트

## 절대 원칙

- **외부 번역/AI API 사용 금지**: Anthropic API, OpenAI API 등 어떤 외부 API도 호출하지 않는다.
  번역은 오직 Claude Code와의 대화 안에서 일괄 처리한다.
- **법적 효력은 인니어 원문에만**: 한국어 번역은 참고용. 모든 사용자 페이지에 면책 조항 필수.

## 번역 워크플로 (이 프로젝트의 핵심)

1. 크롤러가 신규 법령을 DB에 저장할 때 `title_ko`, `summary_ko`를 비워둔다.
2. `python crawler/export_pending.py`를 실행하면 `data/pending/YYYY-MM-DD_<ministry>.md` 파일이 생성된다.
3. 사용자가 그 마크다운 파일 경로를 대화에 던지면, Claude Code는 다음 형식의 JSON을 `translations/<같은이름>.json`으로 저장한다:

   ```json
   [
     {
       "id": 1234,
       "title_ko": "...",
       "summary_ko": "...",
       "categories": ["에너지", "광물자원"],
       "keywords": ["전기차", "배터리"]
     }
   ]
   ```

4. `python crawler/import_translations.py translations/<파일>.json`로 DB에 반영한다.

번역 시 주의:
- 법령 종류(UU, PP, Permen, Kepmen, Perpres 등)는 한국어 표기를 유지하되 원어 약어 병기 (예: "에너지광물자원부 장관령(Permen ESDM)").
- 인명, 회사명, 지명은 인니어 그대로 두고 필요시 한국어 음차 병기.
- summary_ko는 1~2문장으로 간결하게.

## 부처 코드

| code | name_id | name_ko | base_url |
|------|---------|---------|----------|
| dephub | Kementerian Perhubungan | 교통부 | https://jdih.dephub.go.id |
| esdm | Kementerian ESDM | 에너지광물자원부 | https://jdih.esdm.go.id |
| bkpm | BKPM | 투자조정청 | https://jdih.bkpm.go.id |
| kemenkeu | Kementerian Keuangan | 재무부 | https://jdih.kemenkeu.go.id |
| kemendag | Kementerian Perdagangan | 무역부 | https://jdih.kemendag.go.id |
| setneg (kemensetneg) | Kementerian Sekretariat Negara | 국가비서실 | https://jdih.setneg.go.id |

### setneg — 국가 1차 법령 (UU/PP/Perpres) 최속 출처

`crawler/ministries/setneg.py` (`SetnegScraper`). peraturan.go.id 가 해외 IP 차단으로
일일 갱신이 끊긴 자리를, setneg JDIH 의 JSON API 로 대신 채운다. **국가 1차 법령이
가장 빨리 게시되는 공식 출처.**

- 출처 키: `source = "jdih_kemensetneg"`, `ministry_code = "kemensetneg"` (시드의 국가비서실).
  CLI 키는 `setneg` (`python -m crawler.update_all setneg`).
- 수집 타입: UU·Perppu·PP·Perpres·Permensesneg·Keppres·Inpres (7종).
- DOM 스크래핑이 아니라 API 직호출(Playwright 미사용):
  `POST /api/hukumproduk/produkhukum`  body `{"jns":[<코드>],"length":50,"start":<offset>,...}`.
  타입(jns)별 최신순 → 타입별로 따로 페이징(혼합 시 날짜 전역정렬 깨짐). 간헐적 연결
  리셋(WinError 10054) 때문에 호출마다 6회 재시도.
- source_url = `/detailperaturan?jns=<jns>&no=<no>&thn=<thn>`. PDF 는 reCAPTCHA 뒤라 비움.
- 초기 시드: **총 397건.**
  - 고볼륨 국가법령(UU·PP·Perpres·Keppres·Inpres)은 **2025~2026 만** (min_year=2025).
    2024 이전 깊은 과거는 peraturan_go_id 아카이브(34,590건)가 커버 → 중복 회피.
  - setneg 고유 저볼륨 타입은 **전체 이력**: Permensesneg(121, 2005–2024), Perppu(33, 1998–2022).
    이 둘은 2025-2026 발행분이 0건이라 incremental anchor 가 없어 첫 일일 실행에서
    전량 백필됐다(타 출처에 거의 없어 오히려 완전 수집이 이득).
  - 더 과거가 필요하면 `SetnegScraper(min_year=YYYY)` 로 수동 확장 후 dump_jsonl→build_db.
- 일일 갱신: incremental(`known_source_urls`+`stop_after_known=5`)이라 신규분만 가져온다.
  ⚠️ 단, 어떤 타입이 known anchor 를 하나도 안 가지면(예: 새 타입 추가 시) 그 타입은
  stop_after_known 이 안 걸려 **전체 이력을 1회 백필**한다(해당 타입 크기만큼 bounded,
  이후엔 anchor 가 생겨 안정화). 현재 7개 타입은 모두 anchor 보유.
- ⚠️ 중복 주의: laws.db 의 dedup 키는 `UNIQUE(source, source_url)` 라 **source 간 dedup
  이 없다.** 같은 국가법령이 peraturan_go_id / peraturan_bpk 행과 별도로 존재할 수 있다
  (특히 2025). 사이트 표시단 dedup 이 필요하면 `(law_type, law_number, year)` 기준 후속
  패스를 build_db 에 추가할 것.

## 매일 아침 자동 파이프라인 (Windows Task Scheduler)

| 시각 (KST) | 작업 | 스크립트 | 동작 |
|------------|------|----------|------|
| 09:00 | `JDIH-Daily-Update`     | `python -m scripts.daily_update`    | 부처별 incremental 크롤 → `today.summary.json` 생성, 새 행 git push → **setneg 원문 PDF 다운로드 → RAG v2 증분 인덱싱** |
| 10:00 | `JDIH-Daily-Translate`  | `python -m scripts.daily_translate` | 위 summary 의 `chunk_files` 가 비어있지 않으면 `claude -p "/translate-pending" --dangerously-skip-permissions` 호출 → translations/*.json 생성 → import + build_db → git push |

두 작업은 모두 commit/push 까지 자동이라 사이트는 매일 아침 10시 직후 deploy 가 트리거되어 갱신된다.
번역은 **CLAUDE.md 절대 원칙대로 외부 API 미사용** — Claude Code 가 sub-agent 8개 병렬로 청크를 처리한다.
실행 결과는 `data/pending/last_daily_log.txt` (크롤) / `data/pending/last_translate_log.txt` (번역) + 이메일.

### RAG 자동 인덱싱 (daily_update 끝단, 2026-06-09 추가)

`daily_update` 가 crawl/build_db/push 후 두 단계를 더 돈다 (`--no-rag` 로 스킵 가능):

1. `scripts.download_setneg` — `pdf_url_id` 가 있는 신규 setneg 행의 원문 PDF 를
   카테고리 폴더에 다운로드(기존 파일 skip). 신규 없으면 2초 no-op.
2. `rag_incremental_index` — **RAG venv**(`D:\venvs\rag_indonesia_law`, py3.12,
   chromadb 0.5.23 Content-Type 패치본)의 python 으로 `RAG_app/scripts/incremental_v2.py`
   호출 → PyMuPDF 추출 → **RunPod BGE-M3 임베딩** → `v2_indonesia_*` 컬렉션 upsert.
   - ⚠️ 반드시 RAG venv 로 호출(글로벌 py3.14 면 chromadb 패치 부재로 upsert 422).
   - 신규 청크가 있을 때만 RunPod 기동 → 신규 없는 날은 비용 0.
   - 임베딩은 GPU 필요 → 이 머신엔 GPU 가 없어 RunPod 가 유일 경로(RUNPOD_API_KEY 필요).

## 기술 스택

- **크롤러**: Python 3.11+, Playwright (chromium), httpx, BeautifulSoup4
- **DB**: SQLite + FTS5 (한국어/인니어 풀텍스트)
- **웹**: Next.js 15 (App Router, `output: 'export'`), Tailwind CSS, better-sqlite3
- **자동화**: GitHub Actions + Windows Task Scheduler (로컬 호스트에서 일일 크롤·번역)

## 알려진 환경 이슈 (Windows + OneDrive)

- `next dev`는 OneDrive 동기화 폴더에서 `.next/static/<id>` 심볼릭 링크 readlink가 EINVAL로 죽는다.
  → 로컬 검증은 `npm run build && python -m http.server <port> --directory web/out` 으로 정적 export를 직접 서빙한다.
- `better-sqlite3`는 native compile에 Visual Studio가 필요해 설치가 실패한다.
  → Node 22+ 내장 `node:sqlite` (`DatabaseSync`)를 사용한다. 빌드 시 "ExperimentalWarning: SQLite ..." 경고는 무시.
- PowerShell의 `Invoke-WebRequest.Content`는 응답을 비-UTF8로 디코딩해 한글이 깨진다.
  → 검증 시 `RawContentStream`을 가져와 `[System.Text.Encoding]::UTF8.GetString(...)`로 직접 디코딩하거나, 파일에 저장 후 `Read` 도구로 읽는다.

## 자주 하는 작업

- 부처별 스크레이퍼 추가/수정: `crawler/ministries/<code>.py`. `BaseScraper` 상속.
- 스키마 변경: `crawler/db.py`의 `init_db()` 수정. 마이그레이션은 SQL 파일로 `crawler/migrations/`에 추가.
- 신규 페이지 추가: `web/app/` 하위. SSG 호환을 유지할 것 (`generateStaticParams` 필수).
