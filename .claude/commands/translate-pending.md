---
description: Run the daily translation pipeline. Reads data/pending/today.summary.json, dispatches up to 8 sub-agents in parallel to translate each chunk, then imports all translations into the DB.
allowed-tools: Bash, Read, Write, Agent, Glob
---

# 일일 번역 파이프라인

You are running the project's daily translation pipeline. Follow these steps in order:

## 1. Read the day's summary

Read `data/pending/today.summary.json`. It lists `chunk_files: [...]`. If empty,
there is nothing to translate today — say so and stop.

## 2. Verify each chunk file exists

For every path in `chunk_files`, confirm the file exists and is non-empty.
If a file is missing, list it but continue with the rest.

## 3. Dispatch translation sub-agents in parallel

For each chunk file `data/pending/chunks/<ministry>_<date>_NN.json`, launch a
sub-agent with `subagent_type: general-purpose` and `run_in_background: true`,
all in **a single message** so they run concurrently. Use this exact prompt
template, substituting only `<INPUT_PATH>` and `<OUTPUT_PATH>`:

> You are translating Indonesian law titles to Korean. Input is at `<INPUT_PATH>` (JSON array of `{id, title_id, law_type}`). Output a JSON array of `{"id": <int>, "title_ko": "<string>"}` to `<OUTPUT_PATH>`.
>
> Rules:
> - Law type abbreviations get Korean + original-abbrev side-by-side. Examples:
>   - "Keputusan Menteri Energi dan Sumber Daya Mineral Nomor X" → "에너지광물자원부 장관결정(Kepmen ESDM) 제X호"
>   - "Peraturan Menteri ESDM Nomor X" → "에너지광물자원부 장관령(Permen ESDM) 제X호"
>   - "Peraturan Pemerintah Nomor X" → "정부령(PP) 제X호"
>   - "Peraturan Presiden Nomor X" → "대통령령(Perpres) 제X호"
>   - "Keputusan Presiden Nomor X" → "대통령결정(Keppres) 제X호"
>   - "Undang-Undang Nomor X" → "법률(UU) 제X호"
>   - "Surat Edaran Menteri X" → "X부 장관 회람(Surat Edaran)"
>   - "Peraturan Menteri Perdagangan" → "무역부 장관령(Permendag)"
>   - "Peraturan Menteri Ketenagakerjaan" → "인력부 장관령(Permenaker)"
>   - "Peraturan Dirjen Migas" → "석유가스총국장령(Perdirjen Migas)"
>   - 기타 메타 종류(Hasil Analisis, Rancangan PUU, Naskah Akademik, Risalah Pembahasan, Program Penyusunan PUU, Kajian Hukum 등)는 의미 그대로 한국어로 옮기되 원어 병기.
> - Body after "tentang" → 자연스러운 한국어. 인명·회사명·지명은 인니어 그대로 두되 잘 알려진 경우만 한글 음차.
> - "Tahun YYYY" → "YYYY년".
> - "Perubahan atas …" → "…의 개정", "Pencabutan …" → "… 폐지".
> - 약어(BBM, BBG, ICP)는 자명한 경우만 풀어쓰기.
> - 모든 entry 누락 없이 처리. 외부 번역 API 호출 금지.
> - Save with `json.dump(..., indent=1, ensure_ascii=False)`. End with one line: "wrote N entries".

The output path convention: replace `data/pending/chunks/<ministry>_<date>_NN.json`
with `translations/<ministry>_<date>_NN.json`. Make sure the `translations/`
directory exists (`mkdir -p translations`) before dispatch.

## 4. Wait for all sub-agents to complete

Wait for the completion notifications. If any sub-agent fails or reports
fewer entries than the chunk's input, re-dispatch *that single chunk* to a
new sub-agent (do NOT re-do the whole batch).

## 5. Import all translations

```
python -m crawler.import_all_translations
```

## 6. Verify

```
python -X utf8 -c "
from crawler import db
with db.connect() as c:
    r = c.execute('SELECT COUNT(*) FROM laws WHERE title_ko IS NULL').fetchone()[0]
    print(f'remaining untranslated: {r}')
"
```

Report the final count. Do NOT commit or push automatically — the user will
review and run their normal commit flow.
