"""SQLite + FTS5 schema for the Indonesian law search site.

Modeled after Korea's law.go.kr information architecture, mapped to
peraturan.go.id (DITJEN PP, Ministry of Law and Human Rights) data.

Top-level entity is `laws`. Body content (조문/부칙/별표) is stored in
separate child tables so that FTS5 can index them at the right granularity
and so that crawler stages can fill them in incrementally (메타 first,
본문 second).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "laws.db"


SCHEMA = r"""
-- ────────────────────────────────────────────────────────────────────
-- 1) 디멘션: 부처, 지역, 분야
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ministries (
    code        TEXT PRIMARY KEY,            -- 'kemenhub', 'esdm', 'bkpm', ...
    name_id     TEXT NOT NULL,               -- 'Kementerian Perhubungan'
    name_ko     TEXT NOT NULL,               -- '교통부'
    kind        TEXT NOT NULL                -- 'kementerian' | 'lembaga' | 'pemda' | 'mahkamah'
                CHECK (kind IN ('kementerian','lembaga','pemda','mahkamah','lainnya')),
    parent_code TEXT REFERENCES ministries(code) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS regions (
    code      TEXT PRIMARY KEY,              -- 'jabar', 'jakarta', 'bandung-kota', ...
    name_id   TEXT NOT NULL,
    name_ko   TEXT NOT NULL,
    level     TEXT NOT NULL                  -- 'provinsi' | 'kabupaten' | 'kota'
              CHECK (level IN ('provinsi','kabupaten','kota')),
    parent    TEXT REFERENCES regions(code) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS categories (         -- 분야 태그 (사용자 정의)
    code     TEXT PRIMARY KEY,                  -- 'energi', 'investasi', ...
    name_ko  TEXT NOT NULL,
    name_id  TEXT
);

-- ────────────────────────────────────────────────────────────────────
-- 2) 핵심: 법령 (laws)
--    한 행 = 한 개의 법령 문서. 1차 메뉴/위계/지위/시대를 모두 표현.
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS laws (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT UNIQUE,                -- URL-safe id (예: 'uu-12-2023')

    -- 1차 메뉴 매핑 (법제처 좌측 대분류)
    category          TEXT NOT NULL
                      CHECK (category IN (
                          'peraturan',   -- 법령 (UU/PP/Perpres/Permen)
                          'keputusan',   -- 행정규칙 (Kepmen/Surat Edaran)
                          'lampiran',    -- 별표·서식 단독 등록
                          'perda',       -- 지방법규 (Perda/Pergub/Perwali)
                          'putusan',     -- 판례·해석례 (MK/MA)
                          'kepkl',       -- 부처별 결정 (Keputusan K/L)
                          'perjanjian',  -- 국제 조약·협정
                          'lainnya'      -- 기타 (Prolegnas, NA 등)
                      )),

    -- 위계 (UU, PP, Perpres, Permen, Kepmen, Perda, …)
    law_type          TEXT NOT NULL,
    law_number        TEXT NOT NULL,              -- 예: '12 Tahun 2023'
    year              INTEGER,

    -- 제목 / 요약
    title_id          TEXT NOT NULL,              -- 인니어 원제목
    title_ko          TEXT,                       -- 한국어 제목 (Claude Code 번역)
    title_en          TEXT,                       -- peraturan.go.id 공식 영문본
    summary_ko        TEXT,                       -- 한국어 요약 (1~2문장)

    -- 소관 (부처 OR 지역; 둘 다 NULL이면 의회/대통령 등 상위 기관)
    ministry_code     TEXT REFERENCES ministries(code) ON DELETE SET NULL,
    ministry_name_ko  TEXT,                       -- denormalized for fast list view
    region_code       TEXT REFERENCES regions(code) ON DELETE SET NULL,

    -- 일자
    enactment_date    TEXT,                       -- 제정일 Tanggal Penetapan
    promulgation_date TEXT,                       -- 공포일 Tanggal Pengundangan
    effective_date    TEXT,                       -- 시행일
    repealed_date     TEXT,                       -- 폐지일 (status=dicabut)

    -- 상태
    status            TEXT NOT NULL DEFAULT 'berlaku'
                      CHECK (status IN (
                          'berlaku',         -- 현행
                          'diubah',          -- 개정 (일부)
                          'dicabut',         -- 폐지
                          'dicabut_sebagian',-- 일부 폐지
                          'belum_berlaku',   -- 미시행
                          'tidak_diketahui'  -- 미상
                      )),

    -- 시대 구분 (현행 ↔ 근대법령)
    era               TEXT NOT NULL DEFAULT 'modern'
                      CHECK (era IN ('modern','lama','kolonial')),

    -- 출처
    source            TEXT NOT NULL DEFAULT 'peraturan_go_id'
                      CHECK (source IN (
                          'peraturan_go_id',
                          'jdih_dephub','jdih_esdm','jdih_bkpm',
                          'jdih_kemenkeu','jdih_kemendag',
                          'jdih_bnn','jdih_bmkg','jdih_polri',
                          'jdih_kemnaker','jdih_kemenpppa','jdih_brin','jdih_pkp',
                          'mk_go_id','mahkamahagung_go_id',
                          'lainnya'
                      )),
    source_url        TEXT NOT NULL,              -- 원본 페이지
    pdf_url_id        TEXT,                       -- 인니어 PDF 직링크
    pdf_url_en        TEXT,                       -- 공식 영문 PDF (terjemahresmi)

    -- 분야 태그 / 검색 키워드 (JSON 배열로 저장)
    categories        TEXT,                       -- ["energi","minerba"]
    keywords          TEXT,                       -- ["ICP","Pertamina"]

    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (source, source_url)
);

CREATE INDEX IF NOT EXISTS idx_laws_category      ON laws (category);
CREATE INDEX IF NOT EXISTS idx_laws_law_type      ON laws (law_type);
CREATE INDEX IF NOT EXISTS idx_laws_ministry      ON laws (ministry_code);
CREATE INDEX IF NOT EXISTS idx_laws_region        ON laws (region_code);
CREATE INDEX IF NOT EXISTS idx_laws_status        ON laws (status);
CREATE INDEX IF NOT EXISTS idx_laws_era           ON laws (era);
CREATE INDEX IF NOT EXISTS idx_laws_promulgation  ON laws (promulgation_date DESC);
CREATE INDEX IF NOT EXISTS idx_laws_year          ON laws (year DESC);
CREATE INDEX IF NOT EXISTS idx_laws_pending       ON laws (title_ko) WHERE title_ko IS NULL;

-- ────────────────────────────────────────────────────────────────────
-- 3) 연혁 (현재 법령의 모든 버전 체인)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS law_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id          INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,             -- 1=원본, 2=1차 개정, ...
    amended_by_id   INTEGER REFERENCES laws(id) ON DELETE SET NULL,
    effective_from  TEXT,
    effective_to    TEXT,
    change_summary_ko TEXT,
    UNIQUE (law_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_law_versions_law ON law_versions (law_id);

-- ────────────────────────────────────────────────────────────────────
-- 4) 조문 (Pasal) — 조문제목 / 조문내용 검색 지원
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id          INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    article_number  TEXT NOT NULL,                -- 'Pasal 12', 'Pasal 12A'
    chapter         TEXT,                          -- 'BAB III', '제3장'
    section         TEXT,                          -- 'Bagian Kedua'
    title_id        TEXT,                          -- 조 제목 (있을 경우)
    title_ko        TEXT,
    body_id         TEXT,                          -- 조문 본문 (인니어 원문)
    body_ko         TEXT,                          -- 한국어 번역
    ordering        INTEGER NOT NULL DEFAULT 0,    -- 정렬용
    UNIQUE (law_id, article_number)
);

CREATE INDEX IF NOT EXISTS idx_articles_law ON articles (law_id, ordering);

-- ────────────────────────────────────────────────────────────────────
-- 5) 부칙 (Ketentuan Penutup) — 별도 검색 탭
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS addenda (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id    INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    body_id   TEXT NOT NULL,
    body_ko   TEXT,
    UNIQUE (law_id)
);

-- ────────────────────────────────────────────────────────────────────
-- 6) 별표·서식 (Lampiran) — 본법령에 첨부 OR 단독 등록
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attachments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id          INTEGER REFERENCES laws(id) ON DELETE CASCADE,  -- NULL 가능
    lampiran_number TEXT,                          -- 'Lampiran I', 'Lampiran II.A'
    title_id        TEXT NOT NULL,
    title_ko        TEXT,
    file_url        TEXT,                          -- 별표 PDF/엑셀 직링크
    ordering        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_attachments_law ON attachments (law_id, ordering);

-- ────────────────────────────────────────────────────────────────────
-- 7) 제정·개정문 (Penetapan / Perubahan / Pencabutan)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS amendments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id        INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL
                  CHECK (kind IN ('penetapan','perubahan','pencabutan')),
    event_date    TEXT,
    source_law_id INTEGER REFERENCES laws(id) ON DELETE SET NULL,    -- 개정의 근거가 된 법령
    body_id       TEXT,
    body_ko       TEXT
);

CREATE INDEX IF NOT EXISTS idx_amendments_law ON amendments (law_id, event_date);

-- ────────────────────────────────────────────────────────────────────
-- 8) 관련 법령 (Relasi Peraturan)
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id          INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    related_law_id  INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    relation_kind   TEXT NOT NULL                 -- mengubah(개정)/mencabut(폐지)/melaksanakan(시행)/dasar(근거)
                    CHECK (relation_kind IN (
                        'mengubah','dicabut_oleh','mencabut',
                        'melaksanakan','dilaksanakan_oleh','dasar','terkait'
                    )),
    UNIQUE (law_id, related_law_id, relation_kind)
);

CREATE INDEX IF NOT EXISTS idx_relations_law     ON relations (law_id);
CREATE INDEX IF NOT EXISTS idx_relations_related ON relations (related_law_id);

-- ────────────────────────────────────────────────────────────────────
-- 9) 판례 (Putusan MK / Putusan MA) — 1차 메뉴 'putusan'
--    laws 테이블과 별도. 판례는 위계/개정 개념이 다름.
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS court_cases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    court         TEXT NOT NULL                  -- 'MK'(헌법재판소) | 'MA'(대법원) | 'PTUN'(행정법원)
                  CHECK (court IN ('MK','MA','PTUN','PN','lainnya')),
    case_number   TEXT NOT NULL,                 -- 'Putusan No. 91/PUU-XVIII/2020'
    decision_date TEXT,
    title_id      TEXT NOT NULL,
    title_ko      TEXT,
    summary_ko    TEXT,
    keywords      TEXT,                          -- JSON
    related_law_id INTEGER REFERENCES laws(id) ON DELETE SET NULL,  -- 위헌심판 대상 법
    source_url    TEXT NOT NULL,
    pdf_url       TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (court, case_number)
);

CREATE INDEX IF NOT EXISTS idx_court_cases_decision ON court_cases (decision_date DESC);
CREATE INDEX IF NOT EXISTS idx_court_cases_related  ON court_cases (related_law_id);

-- ────────────────────────────────────────────────────────────────────
-- 10) 한·인니 법률용어 사전
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS legal_terms (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id        TEXT NOT NULL,                -- 인니어 표제어
    term_ko        TEXT NOT NULL,                -- 한국어 대응어
    pronunciation  TEXT,                         -- 한글 음차 (예: '뻐라뚜란')
    definition_ko  TEXT,                         -- 한국어 정의
    related_law_id INTEGER REFERENCES laws(id) ON DELETE SET NULL,
    source         TEXT,                         -- 'peraturan.go.id glossary' 등
    UNIQUE (term_id, term_ko)
);

-- ────────────────────────────────────────────────────────────────────
-- 11) 사이트 운영용
-- ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS popular_searches (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    term   TEXT NOT NULL,            -- 'SIUPAL', 'PMA', 'OSS', ...
    rank   INTEGER NOT NULL,
    href   TEXT,                     -- 클릭 시 이동할 검색 URL
    note   TEXT
);

CREATE TABLE IF NOT EXISTS curated_laws (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id    INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    section   TEXT NOT NULL,         -- 'foreign_investment','trade','immigration', ...
    ordering  INTEGER NOT NULL DEFAULT 0,
    note_ko   TEXT
);

CREATE INDEX IF NOT EXISTS idx_curated_laws_section ON curated_laws (section, ordering);

-- ────────────────────────────────────────────────────────────────────
-- 12) FTS5 인덱스 (한국어/인니어 동시 색인, unicode61 토크나이저)
-- ────────────────────────────────────────────────────────────────────

-- 12a) 법령 메타 검색 (제목·요약·키워드)
CREATE VIRTUAL TABLE IF NOT EXISTS laws_fts USING fts5(
    title_id, title_ko, title_en, summary_ko, keywords,
    content='laws', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS laws_ai AFTER INSERT ON laws BEGIN
    INSERT INTO laws_fts (rowid, title_id, title_ko, title_en, summary_ko, keywords)
    VALUES (new.id, new.title_id, new.title_ko, new.title_en, new.summary_ko, new.keywords);
END;
CREATE TRIGGER IF NOT EXISTS laws_ad AFTER DELETE ON laws BEGIN
    INSERT INTO laws_fts (laws_fts, rowid, title_id, title_ko, title_en, summary_ko, keywords)
    VALUES ('delete', old.id, old.title_id, old.title_ko, old.title_en, old.summary_ko, old.keywords);
END;
CREATE TRIGGER IF NOT EXISTS laws_au AFTER UPDATE ON laws BEGIN
    INSERT INTO laws_fts (laws_fts, rowid, title_id, title_ko, title_en, summary_ko, keywords)
    VALUES ('delete', old.id, old.title_id, old.title_ko, old.title_en, old.summary_ko, old.keywords);
    INSERT INTO laws_fts (rowid, title_id, title_ko, title_en, summary_ko, keywords)
    VALUES (new.id, new.title_id, new.title_ko, new.title_en, new.summary_ko, new.keywords);
END;

-- 12b) 조문 검색 (조문제목 + 조문내용)
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_number, title_id, title_ko, body_id, body_ko,
    content='articles', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts (rowid, article_number, title_id, title_ko, body_id, body_ko)
    VALUES (new.id, new.article_number, new.title_id, new.title_ko, new.body_id, new.body_ko);
END;
CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, article_number, title_id, title_ko, body_id, body_ko)
    VALUES ('delete', old.id, old.article_number, old.title_id, old.title_ko, old.body_id, old.body_ko);
END;
CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts (articles_fts, rowid, article_number, title_id, title_ko, body_id, body_ko)
    VALUES ('delete', old.id, old.article_number, old.title_id, old.title_ko, old.body_id, old.body_ko);
    INSERT INTO articles_fts (rowid, article_number, title_id, title_ko, body_id, body_ko)
    VALUES (new.id, new.article_number, new.title_id, new.title_ko, new.body_id, new.body_ko);
END;

-- 12c) 부칙 검색
CREATE VIRTUAL TABLE IF NOT EXISTS addenda_fts USING fts5(
    body_id, body_ko,
    content='addenda', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS addenda_ai AFTER INSERT ON addenda BEGIN
    INSERT INTO addenda_fts (rowid, body_id, body_ko) VALUES (new.id, new.body_id, new.body_ko);
END;
CREATE TRIGGER IF NOT EXISTS addenda_ad AFTER DELETE ON addenda BEGIN
    INSERT INTO addenda_fts (addenda_fts, rowid, body_id, body_ko)
    VALUES ('delete', old.id, old.body_id, old.body_ko);
END;
CREATE TRIGGER IF NOT EXISTS addenda_au AFTER UPDATE ON addenda BEGIN
    INSERT INTO addenda_fts (addenda_fts, rowid, body_id, body_ko)
    VALUES ('delete', old.id, old.body_id, old.body_ko);
    INSERT INTO addenda_fts (rowid, body_id, body_ko) VALUES (new.id, new.body_id, new.body_ko);
END;

-- 12d) 법률용어 사전
CREATE VIRTUAL TABLE IF NOT EXISTS legal_terms_fts USING fts5(
    term_id, term_ko, definition_ko,
    content='legal_terms', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS legal_terms_ai AFTER INSERT ON legal_terms BEGIN
    INSERT INTO legal_terms_fts (rowid, term_id, term_ko, definition_ko)
    VALUES (new.id, new.term_id, new.term_ko, new.definition_ko);
END;
CREATE TRIGGER IF NOT EXISTS legal_terms_ad AFTER DELETE ON legal_terms BEGIN
    INSERT INTO legal_terms_fts (legal_terms_fts, rowid, term_id, term_ko, definition_ko)
    VALUES ('delete', old.id, old.term_id, old.term_ko, old.definition_ko);
END;
CREATE TRIGGER IF NOT EXISTS legal_terms_au AFTER UPDATE ON legal_terms BEGIN
    INSERT INTO legal_terms_fts (legal_terms_fts, rowid, term_id, term_ko, definition_ko)
    VALUES ('delete', old.id, old.term_id, old.term_ko, old.definition_ko);
    INSERT INTO legal_terms_fts (rowid, term_id, term_ko, definition_ko)
    VALUES (new.id, new.term_id, new.term_ko, new.definition_ko);
END;

-- 12e) 판례 검색
CREATE VIRTUAL TABLE IF NOT EXISTS court_cases_fts USING fts5(
    case_number, title_id, title_ko, summary_ko, keywords,
    content='court_cases', content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS court_cases_ai AFTER INSERT ON court_cases BEGIN
    INSERT INTO court_cases_fts (rowid, case_number, title_id, title_ko, summary_ko, keywords)
    VALUES (new.id, new.case_number, new.title_id, new.title_ko, new.summary_ko, new.keywords);
END;
CREATE TRIGGER IF NOT EXISTS court_cases_ad AFTER DELETE ON court_cases BEGIN
    INSERT INTO court_cases_fts (court_cases_fts, rowid, case_number, title_id, title_ko, summary_ko, keywords)
    VALUES ('delete', old.id, old.case_number, old.title_id, old.title_ko, old.summary_ko, old.keywords);
END;
CREATE TRIGGER IF NOT EXISTS court_cases_au AFTER UPDATE ON court_cases BEGIN
    INSERT INTO court_cases_fts (court_cases_fts, rowid, case_number, title_id, title_ko, summary_ko, keywords)
    VALUES ('delete', old.id, old.case_number, old.title_id, old.title_ko, old.summary_ko, old.keywords);
    INSERT INTO court_cases_fts (rowid, case_number, title_id, title_ko, summary_ko, keywords)
    VALUES (new.id, new.case_number, new.title_id, new.title_ko, new.summary_ko, new.keywords);
END;

-- ────────────────────────────────────────────────────────────────────
-- 13) 시드 데이터 (부처/판소 — 변경이 거의 없는 디멘션)
-- ────────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO ministries (code, name_id, name_ko, kind) VALUES
    ('kemenhub',        'Kementerian Perhubungan',                       '교통부',                     'kementerian'),
    ('esdm',            'Kementerian Energi dan Sumber Daya Mineral',    '에너지광물자원부',             'kementerian'),
    ('bkpm',            'Kementerian Investasi/BKPM',                    '투자조정청',                  'kementerian'),
    ('kemenkeu',        'Kementerian Keuangan',                          '재무부',                     'kementerian'),
    ('kemendag',        'Kementerian Perdagangan',                       '무역부',                     'kementerian'),
    ('kumham',          'Kementerian Hukum dan HAM',                     '법무인권부',                  'kementerian'),
    ('kemenhut',        'Kementerian Kehutanan',                         '산림부',                     'kementerian'),
    ('kementan',        'Kementerian Pertanian',                         '농업부',                     'kementerian'),
    ('kemenkes',        'Kementerian Kesehatan',                         '보건부',                     'kementerian'),
    ('kemenag',         'Kementerian Agama',                             '종교부',                     'kementerian'),
    ('kemensos',        'Kementerian Sosial',                            '사회부',                     'kementerian'),
    ('kemenkopukm',     'Kementerian Koperasi dan UKM',                  '협동조합·중소기업부',           'kementerian'),
    ('kemenpkp',        'Kementerian Perumahan dan Kawasan Permukiman',  '주거단지부',                  'kementerian'),
    ('kemenpera',       'Kementerian Perumahan Rakyat',                  '주거공급부(구)',              'kementerian'),
    ('kemenpu',         'Kementerian Pekerjaan Umum',                    '공공사업부',                  'kementerian'),
    ('kemenkkp',        'Kementerian Kelautan dan Perikanan',            '해양수산부',                  'kementerian'),
    ('kemenpar',        'Kementerian Pariwisata',                        '관광부',                     'kementerian'),
    ('kemenkominfo',    'Kementerian Komunikasi dan Informatika',        '통신정보부(구)',               'kementerian'),
    ('kemenkomdigi',    'Kementerian Komunikasi dan Digital',            '통신디지털부',                 'kementerian'),
    ('kemenperin',      'Kementerian Perindustrian',                     '산업부',                     'kementerian'),
    ('kemendikdasmen',  'Kementerian Pendidikan Dasar dan Menengah',     '초중등교육부',                 'kementerian'),
    ('kemenkebud',      'Kementerian Kebudayaan',                        '문화부',                     'kementerian'),
    ('kemenpanrb',      'Kementerian Pendayagunaan Aparatur Negara dan Reformasi Birokrasi', '행정개혁부', 'kementerian'),
    ('kemenkoinfra',    'Kementerian Koordinator Infrastruktur dan Pembangunan Kewilayahan', '인프라·지역개발 조정부', 'kementerian'),
    ('kemenpppa',       'Kementerian Pemberdayaan Perempuan dan Perlindungan Anak', '여성·아동권익부',     'kementerian'),
    ('bappenas',        'Kementerian PPN/Bappenas',                      '국가개발기획부',               'kementerian'),
    ('atrbpn',          'Kementerian ATR/BPN',                           '토지·공간행정부',              'kementerian'),
    ('kemendagri',      'Kementerian Dalam Negeri',                      '내무부',                     'kementerian'),
    ('kemendikbud',     'Kementerian Pendidikan dan Kebudayaan',         '교육문화부(구)',               'kementerian'),
    ('kemenhan',        'Kementerian Pertahanan',                        '국방부',                     'kementerian'),
    ('kemenristek',     'Kementerian Riset dan Teknologi',               '연구기술부',                  'kementerian'),
    ('kemendiktisaintek','Kementerian Pendidikan Tinggi, Sains, dan Teknologi', '고등과학기술부',       'kementerian'),
    ('kemenaker',       'Kementerian Ketenagakerjaan',                   '인력부',                     'kementerian'),
    ('kemendesa',       'Kementerian Desa, PDT, dan Transmigrasi',       '마을부',                     'kementerian'),
    ('kemenlu',         'Kementerian Luar Negeri',                       '외무부',                     'kementerian'),
    ('kemenlh',         'Kementerian Lingkungan Hidup',                  '환경부',                     'kementerian'),
    ('kemenpora',       'Kementerian Pemuda dan Olahraga',               '청년체육부',                  'kementerian'),
    ('kemensetneg',     'Kementerian Sekretariat Negara',                '국가비서실',                  'kementerian'),
    ('kemenparekraf',   'Kementerian Pariwisata dan Ekonomi Kreatif',    '관광·창조경제부(구)',           'kementerian'),
    ('kemenimipas',     'Kementerian Imigrasi dan Pemasyarakatan',       '이민·교정부',                  'kementerian'),
    ('kemenko',         'Kementerian Koordinator',                       '조정부(전반)',                'kementerian'),
    ('bnn',             'Badan Narkotika Nasional',                      '마약수사청',                  'lembaga'),
    ('bmkg',            'Badan Meteorologi, Klimatologi, dan Geofisika', '기상기후지구물리청',           'lembaga'),
    ('polri',           'Kepolisian Negara Republik Indonesia',          '국가경찰청',                  'lembaga'),
    ('brin',            'Badan Riset dan Inovasi Nasional',              '국가연구혁신청',              'lembaga'),
    ('mk',              'Mahkamah Konstitusi',                           '헌법재판소',                  'mahkamah'),
    ('ma',              'Mahkamah Agung',                                '대법원',                     'mahkamah');
"""


# ────────────────────────────────────────────────────────────────────
#  Connection / lifecycle helpers
# ────────────────────────────────────────────────────────────────────

@contextmanager
def connect(path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(path: Path | str = DB_PATH) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


# ────────────────────────────────────────────────────────────────────
#  Upsert / query helpers (필요한 것만 유지, 신규 스키마 기준)
# ────────────────────────────────────────────────────────────────────

def upsert_law(conn: sqlite3.Connection, row: dict) -> int:
    """Insert or update a law by (source, source_url).

    Translation fields (title_ko, summary_ko, categories, keywords) and
    body fields (조문/부칙/별표는 별도 테이블) are *not* overwritten on
    re-crawl — the crawler only updates metadata.
    """
    if isinstance(row.get("categories"), (list, tuple)):
        row["categories"] = json.dumps(row["categories"], ensure_ascii=False)
    if isinstance(row.get("keywords"), (list, tuple)):
        row["keywords"] = json.dumps(row["keywords"], ensure_ascii=False)

    row.setdefault("updated_at", datetime.utcnow().isoformat(timespec="seconds"))

    defaults = {
        "slug": None, "title_ko": None, "title_en": None, "summary_ko": None,
        "ministry_code": None, "ministry_name_ko": None, "region_code": None,
        "year": None,
        "enactment_date": None, "promulgation_date": None,
        "effective_date": None, "repealed_date": None,
        "status": "berlaku", "era": "modern",
        "source": "peraturan_go_id",
        "pdf_url_id": None, "pdf_url_en": None,
        "categories": None, "keywords": None,
    }
    payload = {**defaults, **row}

    sql = """
    INSERT INTO laws (
        slug, category, law_type, law_number, year,
        title_id, title_ko, title_en, summary_ko,
        ministry_code, ministry_name_ko, region_code,
        enactment_date, promulgation_date, effective_date, repealed_date,
        status, era,
        source, source_url, pdf_url_id, pdf_url_en,
        categories, keywords, updated_at
    ) VALUES (
        :slug, :category, :law_type, :law_number, :year,
        :title_id, :title_ko, :title_en, :summary_ko,
        :ministry_code, :ministry_name_ko, :region_code,
        :enactment_date, :promulgation_date, :effective_date, :repealed_date,
        :status, :era,
        :source, :source_url, :pdf_url_id, :pdf_url_en,
        :categories, :keywords, :updated_at
    )
    ON CONFLICT (source, source_url) DO UPDATE SET
        category          = excluded.category,
        law_type          = excluded.law_type,
        law_number        = excluded.law_number,
        year              = excluded.year,
        title_id          = excluded.title_id,
        ministry_code     = excluded.ministry_code,
        ministry_name_ko  = excluded.ministry_name_ko,
        region_code       = excluded.region_code,
        enactment_date    = excluded.enactment_date,
        promulgation_date = excluded.promulgation_date,
        effective_date    = excluded.effective_date,
        repealed_date     = excluded.repealed_date,
        status            = excluded.status,
        era               = excluded.era,
        pdf_url_id        = excluded.pdf_url_id,
        pdf_url_en        = excluded.pdf_url_en,
        updated_at        = excluded.updated_at
    """
    cur = conn.execute(sql, payload)
    if cur.lastrowid:
        return cur.lastrowid
    found = conn.execute(
        "SELECT id FROM laws WHERE source=? AND source_url=?",
        (payload["source"], payload["source_url"]),
    ).fetchone()
    return found["id"]


def pending_translations(conn: sqlite3.Connection,
                         ministry_code: str | None = None,
                         category: str | None = None,
                         limit: int = 200) -> list[sqlite3.Row]:
    where = ["title_ko IS NULL"]
    params: list = []
    if ministry_code:
        where.append("ministry_code = ?")
        params.append(ministry_code)
    if category:
        where.append("category = ?")
        params.append(category)
    sql = (
        "SELECT * FROM laws WHERE " + " AND ".join(where)
        + " ORDER BY promulgation_date DESC, id DESC LIMIT ?"
    )
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def apply_translation(conn: sqlite3.Connection, *,
                      law_id: int,
                      title_ko: str,
                      summary_ko: str | None = None,
                      categories: Iterable[str] | None = None,
                      keywords: Iterable[str] | None = None) -> None:
    conn.execute(
        """
        UPDATE laws
           SET title_ko   = ?,
               summary_ko = COALESCE(?, summary_ko),
               categories = COALESCE(?, categories),
               keywords   = COALESCE(?, keywords),
               updated_at = CURRENT_TIMESTAMP
         WHERE id = ?
        """,
        (
            title_ko,
            summary_ko,
            json.dumps(list(categories), ensure_ascii=False) if categories else None,
            json.dumps(list(keywords), ensure_ascii=False) if keywords else None,
            law_id,
        ),
    )


if __name__ == "__main__":
    init_db()
    print(f"Initialized DB at {DB_PATH}")
