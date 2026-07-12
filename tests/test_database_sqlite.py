"""
database.py 의 SQLite 백엔드(배포용 exe 전용 경로) 테스트.
실제로는 sys.frozen 일 때만 자동 선택되지만, 여기서는 monkeypatch로 DB_BACKEND/SQLITE_PATH를
강제로 sqlite로 바꿔 격리된 tmp_path DB 파일에서 검증한다(MySQL 서버 불필요).
"""
import datetime

import pytest

from src import database, init_db


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """격리된 SQLite 파일로 database.py/init_db.py 를 모두 sqlite 모드로 몽키패치하고
    스키마까지 적용한 뒤 경로를 반환."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_BACKEND", "sqlite")
    monkeypatch.setattr(database, "SQLITE_PATH", db_path)
    monkeypatch.setattr(init_db, "DB_BACKEND", "sqlite")
    monkeypatch.setattr(init_db, "SQLITE_PATH", db_path)
    init_db.ensure_schema()
    return db_path


def test_ensure_schema_creates_expected_tables(sqlite_db):
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            names = {r["name"] for r in cur.fetchall()}
    finally:
        conn.close()
    assert {"messages", "training_runs", "user_reports", "trusted_senders"} <= names


def test_ensure_schema_is_idempotent(sqlite_db):
    tables_again = init_db.ensure_schema()   # 두 번째 호출도 에러 없이 동일 결과
    assert "messages" in tables_again


def test_save_prediction_and_fetch_recent_roundtrip(sqlite_db):
    database.save_prediction("본문내용", "spam", 0.91, sender="a@b.com", source="manual")
    rows = database.fetch_recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["content"] == "본문내용"
    assert rows[0]["predicted_label"] == "spam"
    # MySQL(pymysql)과 동일하게 TIMESTAMP 컬럼이 datetime 객체로 와야 함(app.py의 .strftime() 호출과 호환)
    assert isinstance(rows[0]["created_at"], datetime.datetime)


def test_fetch_stats_counts_by_tier(sqlite_db):
    database.save_prediction("c1", "spam", 0.9)
    database.save_prediction("c2", "ham", 0.1)
    database.save_prediction("c3", "review", 0.5)
    stats = database.fetch_stats()
    assert stats["total"] == 3
    assert stats["spam_count"] == 1
    assert stats["ham_count"] == 1
    assert stats["review_count"] == 1


def test_trusted_sender_upsert_insert_then_update_on_conflict(sqlite_db):
    database.add_trusted_sender("a@b.com", note="first")
    database.add_trusted_sender("a@b.com", note="updated")   # 같은 pattern -> UPDATE 되어야 함(중복 에러 X)
    rows = database.fetch_trusted_senders()
    assert len(rows) == 1
    assert rows[0]["note"] == "updated"
    assert database.is_trusted("A@B.COM")   # 대소문자 무관 매칭(정규화 저장)


def test_gmail_id_unique_constraint_allows_multiple_nulls(sqlite_db):
    # gmail_id가 NULL인 수동입력 메시지가 여러 건이어도 UNIQUE 제약에 걸리면 안 됨
    database.save_prediction("m1", "ham", 0.1, source="manual", gmail_id=None)
    database.save_prediction("m2", "ham", 0.1, source="manual", gmail_id=None)
    assert len(database.fetch_recent(limit=10)) == 2
