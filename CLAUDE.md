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

## 매일 아침 자동 파이프라인 (Windows Task Scheduler)

| 시각 (KST) | 작업 | 스크립트 | 동작 |
|------------|------|----------|------|
| 09:00 | `JDIH-Daily-Update`     | `python -m scripts.daily_update`    | 부처별 incremental 크롤 → `data/pending/today.summary.json` 생성, 새 행 git push |
| 10:00 | `JDIH-Daily-Translate`  | `python -m scripts.daily_translate` | 위 summary 의 `chunk_files` 가 비어있지 않으면 `claude -p "/translate-pending" --dangerously-skip-permissions` 호출 → translations/*.json 생성 → import + build_db → git push |

두 작업은 모두 commit/push 까지 자동이라 사이트는 매일 아침 10시 직후 deploy 가 트리거되어 갱신된다.
번역은 **CLAUDE.md 절대 원칙대로 외부 API 미사용** — Claude Code 가 sub-agent 8개 병렬로 청크를 처리한다.
실행 결과는 `data/pending/last_daily_log.txt` (크롤) / `data/pending/last_translate_log.txt` (번역) + 이메일.

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
