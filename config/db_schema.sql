-- ============================================
--  Spam Detector - MySQL 스키마
--  실행: mysql -u root -p < config/db_schema.sql
-- ============================================

CREATE DATABASE IF NOT EXISTS spam_detector
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE spam_detector;

-- 1) 분석한 메시지 원본 + 예측 결과
CREATE TABLE IF NOT EXISTS messages (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    source        VARCHAR(50)  DEFAULT 'manual',   -- 'manual', 'gmail', 'import' 등
    gmail_id      VARCHAR(255) DEFAULT NULL,        -- Gmail 메시지 ID (중복 방지·조치용)
    sender        VARCHAR(255),                     -- 발신자 (있으면)
    content       TEXT         NOT NULL,            -- 메시지 본문
    predicted_label ENUM('ham','spam') NOT NULL,    -- 예측 결과 (표시는 3단계, 저장은 이진)
    spam_prob     FLOAT        NOT NULL,            -- 스팸 확률 (0.0 ~ 1.0)
    model_version VARCHAR(50)  DEFAULT 'v1',
    actioned      TINYINT(1)   DEFAULT 0,           -- 사용자 조치 완료 여부 (Gmail 목록에서 숨김)
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_gmail (gmail_id),                 -- 같은 Gmail 메일 중복 저장 방지
    INDEX idx_label (predicted_label),
    INDEX idx_created (created_at)
);

-- 2) 학습 실행 성능 로그
CREATE TABLE IF NOT EXISTS training_runs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    model_version VARCHAR(50),
    train_size    INT,
    test_size     INT,
    accuracy      FLOAT,
    precision_val FLOAT,
    recall_val    FLOAT,
    f1_score      FLOAT,
    trained_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3) 사용자가 직접 등록한 스팸/정상 (피드백 -> 재학습 데이터)
CREATE TABLE IF NOT EXISTS user_reports (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    content    TEXT NOT NULL,                    -- 등록한 메시지 본문
    user_label ENUM('ham','spam') NOT NULL,      -- 사용자가 지정한 정답
    note       VARCHAR(255),                     -- 메모(선택)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4) 신뢰 발신자 (allowlist) — 이 발신자는 모델과 무관하게 정상 처리
CREATE TABLE IF NOT EXISTS trusted_senders (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    pattern    VARCHAR(255) NOT NULL UNIQUE,     -- 이메일주소 또는 도메인 (소문자)
    note       VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
