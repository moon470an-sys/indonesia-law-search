# 인도네시아 법령 한국어 검색 사이트

인도네시아 5개 부처(교통부, ESDM, BKPM, 재무부, 무역부)의 JDIH 법령 정보를 매일 수집하고, 한국어로 번역하여 정적 검색 사이트로 제공합니다.

## 핵심 원칙

- **외부 번역 API 미사용**: 번역은 Claude Code와의 대화 중 일괄 처리.
- **정적 우선**: SQLite + Next.js SSG로 단순 운영.
- **법적 효력은 원문에만**: 모든 페이지에 면책 조항 표시.

## 디렉토리 구조

```
crawler/        # Python + Playwright 크롤러
data/           # SQLite DB와 번역 대기 마크다운
translations/   # 번역 완료 JSON 히스토리
web/            # Next.js 정적 사이트
scripts/        # 빌드/유틸 스크립트
.github/        # GitHub Actions
```

## 일일 워크플로

1. GitHub Actions가 매일 새벽 5개 부처 JDIH 크롤링
2. 신규 법령은 `data/laws.db`에 메타정보만 저장 (`title_ko IS NULL`)
3. `crawler/export_pending.py`가 미번역 법령을 `data/pending/YYYY-MM-DD_<ministry>.md`로 export
4. 사용자가 해당 마크다운을 Claude Code에 붙여넣어 번역 요청
5. Claude Code가 번역 JSON을 `translations/`에 저장 → `crawler/import_translations.py`로 DB 반영
6. Next.js 빌드 → 정적 호스팅에 배포

## 셋업

```bash
# 크롤러
cd crawler
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 웹
cd web
npm install
npm run dev
```

## 면책

본 한국어 번역은 참고용이며, 법적 효력은 인니어 원문에만 있습니다.
