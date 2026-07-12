-- ============================================
--  Spam Detector - SQLite 스키마 (배포용 exe 전용)
--  MySQL 스키마(db_schema.sql)의 SQLite 대응판. sys.frozen 일 때 init_db.ensure_schema()가
--  자동으로 이 파일을 적용한다(개발 환경은 계속 db_schema.sql/MySQL 사용).
--  ENUM -> CHECK, AUTO_INCREMENT -> INTEGER PRIMARY KEY AUTOINCREMENT, information_schema 불필요.
-- ============================================

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT DEFAULT 'manual',
    gmail_id        TEXT DEFAULT NULL UNIQUE,
    sender          TEXT,
    content         TEXT NOT NULL,
    predicted_label TEXT NOT NULL CHECK(predicted_label IN ('ham','review','spam')),
    spam_prob       REAL NOT NULL,
    model_version   TEXT DEFAULT 'v1',
    actioned        INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_label ON messages(predicted_label);
CREATE INDEX IF NOT EXISTS idx_created ON messages(created_at);

CREATE TABLE IF NOT EXISTS training_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version TEXT,
    train_size    INTEGER,
    test_size     INTEGER,
    accuracy      REAL,
    precision_val REAL,
    recall_val    REAL,
    f1_score      REAL,
    trained_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT NOT NULL,
    user_label TEXT NOT NULL CHECK(user_label IN ('ham','spam')),
    note       TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trusted_senders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern    TEXT NOT NULL UNIQUE,
    note       TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
