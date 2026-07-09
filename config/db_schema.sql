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
    sender        VARCHAR(255),                     -- 발신자 (있으면)
    content       TEXT         NOT NULL,            -- 메시지 본문
    predicted_label ENUM('ham','spam') NOT NULL,    -- 예측 결과
    spam_prob     FLOAT        NOT NULL,            -- 스팸 확률 (0.0 ~ 1.0)
    model_version VARCHAR(50)  DEFAULT 'v1',
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,

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
