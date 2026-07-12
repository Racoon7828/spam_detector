"""
DB 초기화: 스키마를 실행해 데이터베이스와 테이블을 생성한다.
멱등(idempotent) — 이미 최신 상태면 아무 것도 바뀌지 않으므로 반복 호출해도 안전하다.
`ensure_schema()`는 `main.py`의 앱 실행 경로에서 시작 시 자동 호출되어, 패키징된 배포판에서도
사용자가 이 스크립트를 직접 실행할 필요 없이 최초 1회 스키마가 자동 준비되게 한다.

백엔드는 config.DB_BACKEND 로 자동 선택됨(개발=MySQL, 배포용 exe=SQLite). SQLite는 새 백엔드라
기존 버전이 없으므로 마이그레이션 없이 스키마만 적용하면 된다(훨씬 단순함).

실행(CLI): python src/init_db.py
"""
import os
import sys
import sqlite3

import pymysql

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import DB_CONFIG, DB_BACKEND, SQLITE_PATH
from src.logger_config import get_logger

logger = get_logger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(_ROOT, "config", "db_schema.sql")
SQLITE_SCHEMA_PATH = os.path.join(_ROOT, "config", "db_schema_sqlite.sql")


def ensure_schema():
    """DB·테이블이 없으면 생성, 있으면 필요한 마이그레이션만 적용. 연결 실패 시 예외를
    그대로 전파한다(호출자가 CLI 안내 메시지를 낼지, 조용히 경고만 남길지 결정)."""
    if DB_BACKEND == "sqlite":
        return _ensure_schema_sqlite()
    return _ensure_schema_mysql()


def _ensure_schema_sqlite():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        with open(SQLITE_SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())   # CREATE TABLE IF NOT EXISTS 라 멱등
        conn.commit()
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    finally:
        conn.close()
    logger.info(f"DB 스키마 점검 완료(sqlite): {SQLITE_PATH} (테이블: {tables})")
    return tables


def _ensure_schema_mysql():
    # 스키마가 데이터베이스를 생성하므로, database 지정 없이 접속
    conf = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    conn = pymysql.connect(**conf)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            raw = f.read()

        # 주석(--) 제거 후 세미콜론 단위로 실행
        lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
        statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

        with conn.cursor() as cur:
            for st in statements:
                cur.execute(st)
        conn.commit()

        # --- 마이그레이션: 기존 messages 테이블에 gmail_id 없으면 추가 ---
        with conn.cursor() as cur:
            cur.execute("USE spam_detector")
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema='spam_detector' AND table_name='messages' "
                "AND column_name='gmail_id'"
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE messages ADD COLUMN gmail_id VARCHAR(255) DEFAULT NULL")
                cur.execute("ALTER TABLE messages ADD UNIQUE KEY uq_gmail (gmail_id)")
                logger.info("마이그레이션: messages.gmail_id 추가")
            # actioned 컬럼 (사용자 조치 완료 -> Gmail 목록에서 숨김)
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema='spam_detector' AND table_name='messages' "
                "AND column_name='actioned'"
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE messages ADD COLUMN actioned TINYINT(1) DEFAULT 0")
                logger.info("마이그레이션: messages.actioned 추가")
            # predicted_label 에 'review' 없으면 3단계 ENUM으로 확장 (Reviewer 지적: 이진저장-3단계표시 불일치)
            cur.execute(
                "SELECT COLUMN_TYPE FROM information_schema.columns "
                "WHERE table_schema='spam_detector' AND table_name='messages' "
                "AND column_name='predicted_label'"
            )
            col_type = cur.fetchone()[0]
            if "review" not in col_type:
                cur.execute(
                    "ALTER TABLE messages MODIFY predicted_label "
                    "ENUM('ham','review','spam') NOT NULL"
                )
                logger.info("마이그레이션: messages.predicted_label 에 'review' 추가(3단계)")
        conn.commit()

        # 결과 확인
        with conn.cursor() as cur:
            cur.execute("USE spam_detector")
            cur.execute("SHOW TABLES")
            tables = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    logger.info(f"DB 스키마 점검 완료(mysql): spam_detector (테이블: {tables})")
    return tables


def main():
    try:
        tables = ensure_schema()
    except Exception as e:
        raise SystemExit(f"DB 연결/초기화 실패: {e}\nconfig/config.py 의 접속정보를 확인하세요.")
    print(f"DB 초기화 완료 ({DB_BACKEND})")
    print("생성된 테이블:", tables)


if __name__ == "__main__":
    main()
