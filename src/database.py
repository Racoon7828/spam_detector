"""
MySQL 연동 헬퍼.
예측 결과 저장 / 조회 / 통계 집계.
"""
import pymysql

try:
    from config.config import DB_CONFIG
except ImportError:
    raise SystemExit(
        "config/config.py 가 없습니다. "
        "config/config.example.py 를 복사해서 만들어 주세요."
    )


def get_connection():
    """MySQL 커넥션 반환."""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def save_prediction(content, predicted_label, spam_prob,
                    sender=None, source="manual", model_version="v1"):
    """한 건의 예측 결과를 messages 테이블에 저장."""
    sql = """
        INSERT INTO messages
            (source, sender, content, predicted_label, spam_prob, model_version)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (source, sender, content,
                              predicted_label, spam_prob, model_version))
        conn.commit()
    finally:
        conn.close()


def fetch_recent(limit=20):
    """최근 예측 결과 조회."""
    sql = "SELECT * FROM messages ORDER BY created_at DESC LIMIT %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return cur.fetchall()
    finally:
        conn.close()


def fetch_stats():
    """전체 통계 (총계 / 스팸 / 정상)."""
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(predicted_label = 'spam') AS spam_count,
            SUM(predicted_label = 'ham')  AS ham_count
        FROM messages
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()
    finally:
        conn.close()


def save_report(content, user_label, note=None):
    """사용자가 직접 등록한 스팸/정상(정답)을 user_reports 에 저장."""
    sql = "INSERT INTO user_reports (content, user_label, note) VALUES (%s, %s, %s)"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (content, user_label, note))
        conn.commit()
    finally:
        conn.close()


def fetch_reports(limit=20):
    """사용자 등록 목록 조회."""
    sql = "SELECT * FROM user_reports ORDER BY created_at DESC LIMIT %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            return cur.fetchall()
    finally:
        conn.close()


def count_reports():
    """사용자 등록 수 (스팸/정상)."""
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(user_label = 'spam') AS spam_count,
            SUM(user_label = 'ham')  AS ham_count
        FROM user_reports
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()
    finally:
        conn.close()
