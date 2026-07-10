"""
MySQL 연동 헬퍼.
예측 결과 저장 / 조회 / 통계 집계 / 신뢰 발신자(allowlist).
"""
import re
import pymysql

from src.logger_config import get_logger

logger = get_logger(__name__)

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")


def extract_email(sender):
    """'홍길동 <a@b.com>' 같은 발신자 문자열에서 이메일만 소문자로 추출."""
    if not sender:
        return ""
    m = _EMAIL_RE.search(str(sender))
    return m.group(0).lower() if m else str(sender).strip().lower()

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
                    sender=None, source="manual", model_version="v1",
                    gmail_id=None):
    """한 건의 예측 결과를 messages 테이블에 저장. (gmail_id 있으면 중복 무시)"""
    sql = """
        INSERT INTO messages
            (source, gmail_id, sender, content, predicted_label, spam_prob, model_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (source, gmail_id, sender, content,
                              predicted_label, spam_prob, model_version))
        conn.commit()
    finally:
        conn.close()


def existing_gmail_ids():
    """이미 저장된 Gmail 메시지 ID 집합 (중복 저장 방지용)."""
    sql = "SELECT gmail_id FROM messages WHERE gmail_id IS NOT NULL"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return {row["gmail_id"] for row in cur.fetchall()}
    finally:
        conn.close()


def _label_filter_clause(label):
    """label='spam' -> ('spam','review') 로 묶어서 매칭 (검토도 주의 필요 항목이라 스팸 탭에 포함,
    predicted_label 이 3단계(ham/review/spam)로 바뀐 뒤에도 기존 [스팸] 필터가 계속
    같은 범위를 보여주도록 하기 위함). label='ham' -> 'ham' 만. None -> 필터 없음."""
    if label == "spam":
        return " AND predicted_label IN ('spam','review')", []
    if label == "ham":
        return " AND predicted_label=%s", ["ham"]
    return "", []


def fetch_gmail_pending(limit=20, offset=0, label="spam"):
    """조치하지 않은(actioned=0) Gmail 메일 목록 (페이지네이션 + 라벨 필터).
    label: 'spam'(기본, 스팸+검토) | 'ham'(정상만) | None(전체)."""
    where = "source='gmail' AND gmail_id IS NOT NULL AND actioned=0"
    extra, params = _label_filter_clause(label)
    where += extra
    params += [limit, offset]
    sql = f"SELECT * FROM messages WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
    finally:
        conn.close()


def count_gmail_pending(label="spam"):
    """미조치 Gmail 메일 총 개수 (페이지 계산용). label 필터 동일."""
    where = "source='gmail' AND gmail_id IS NOT NULL AND actioned=0"
    extra, params = _label_filter_clause(label)
    where += extra
    sql = f"SELECT COUNT(*) AS n FROM messages WHERE {where}"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchone()["n"]
    finally:
        conn.close()


def mark_gmail_actioned(gmail_ids):
    """선택한 Gmail 메일을 조치완료 표시 -> 목록에서 숨김 (기록/통계는 보존)."""
    if not gmail_ids:
        return
    placeholders = ",".join(["%s"] * len(gmail_ids))
    sql = f"UPDATE messages SET actioned=1 WHERE gmail_id IN ({placeholders})"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(gmail_ids))
        conn.commit()
    finally:
        conn.close()


def get_content_by_gmail_id(gmail_id):
    """gmail_id 로 저장된 본문 조회 (피드백 등록용). 없으면 None."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT content FROM messages WHERE gmail_id = %s LIMIT 1",
                        (gmail_id,))
            row = cur.fetchone()
            return row["content"] if row else None
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
    """전체 통계 (총계 / 스팸 / 검토 / 정상). predicted_label 이 3단계라 스팸/정상은
    확정된 것만 세고(review 제외), review_count 로 애매한 건수를 별도 노출."""
    sql = """
        SELECT
            COUNT(*) AS total,
            SUM(predicted_label = 'spam')   AS spam_count,
            SUM(predicted_label = 'review') AS review_count,
            SUM(predicted_label = 'ham')    AS ham_count
        FROM messages
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()
    finally:
        conn.close()


def save_report(content, user_label, note=None, trigger_retrain=True):
    """사용자가 직접 등록한 스팸/정상(정답)을 user_reports 에 저장.
    저장 후 자동 재학습 임계치를 체크(백그라운드, 논블로킹) -> 쌓이면 자동 재학습+배포.
    trigger_retrain=False 로 두면 이 호출에서는 체크를 생략한다(벌크 처리용 —
    N건을 반복 저장할 때마다 매번 스레드+전체조회 하지 않도록, 호출측이 루프 종료 후
    trigger_retrain_check() 를 한 번만 부르게 하기 위함)."""
    sql = "INSERT INTO user_reports (content, user_label, note) VALUES (%s, %s, %s)"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (content, user_label, note))
        conn.commit()
    finally:
        conn.close()

    if trigger_retrain:
        trigger_retrain_check()


def trigger_retrain_check():
    """자동 재학습 임계치 체크(백그라운드, 논블로킹)를 1회 실행.
    save_report(trigger_retrain=False) 로 여러 건 저장한 뒤 마지막에 한 번만 호출할 것."""
    try:
        from src.auto_retrain import check_and_retrain_async
        check_and_retrain_async()
    except Exception as e:
        logger.error(f"auto_retrain 체크 생략: {e}")


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


# ---------- 신뢰 발신자 (allowlist) ----------
def add_trusted_sender(pattern, note=None):
    """신뢰 발신자 추가. pattern = 이메일주소 또는 도메인 (예: 'a@b.com' 또는 'b.com')."""
    pattern = (pattern or "").strip().lower()
    if not pattern:
        return
    sql = ("INSERT INTO trusted_senders (pattern, note) VALUES (%s, %s) "
           "ON DUPLICATE KEY UPDATE note = VALUES(note)")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (pattern, note))
        conn.commit()
    finally:
        conn.close()


def remove_trusted_sender(pattern):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM trusted_senders WHERE pattern = %s",
                        ((pattern or "").strip().lower(),))
        conn.commit()
    finally:
        conn.close()


def fetch_trusted_senders():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM trusted_senders ORDER BY created_at DESC")
            return cur.fetchall()
    finally:
        conn.close()


def add_trusted_from_sender(sender, use_domain=False):
    """발신자 문자열('홍길동 <a@b.com>')에서 이메일/도메인을 추출해 신뢰 등록.
    use_domain=True 면 도메인(b.com) 전체, False 면 이메일 주소만. 등록한 pattern 반환."""
    email = extract_email(sender)
    if not email:
        return None
    pattern = email.split("@")[-1] if (use_domain and "@" in email) else email
    add_trusted_sender(pattern, note="from_list")
    return pattern


def trust_senders_by_gmail_ids(gmail_ids, use_domain=False):
    """선택한 Gmail 메일들의 발신자를 신뢰 목록에 일괄 등록 (목록에서 클릭 등록용).
    등록된 pattern 목록 반환."""
    added = []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for gid in gmail_ids:
                cur.execute("SELECT sender FROM messages WHERE gmail_id=%s LIMIT 1", (gid,))
                row = cur.fetchone()
                if not row or not row.get("sender"):
                    continue
                email = extract_email(row["sender"])
                if not email:
                    continue
                pattern = email.split("@")[-1] if (use_domain and "@" in email) else email
                cur.execute(
                    "INSERT INTO trusted_senders (pattern, note) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE note=VALUES(note)", (pattern, "from_list"))
                if pattern not in added:
                    added.append(pattern)
        conn.commit()
    finally:
        conn.close()
    return added


def is_trusted(sender):
    """발신자가 신뢰 목록에 있으면 True. 이메일 정확 매칭 또는 도메인 매칭."""
    email = extract_email(sender)
    if not email:
        return False
    domain = email.split("@")[-1] if "@" in email else ""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pattern FROM trusted_senders")
            patterns = {row["pattern"] for row in cur.fetchall()}
    finally:
        conn.close()
    if email in patterns:                       # 이메일 정확 매칭
        return True
    for p in patterns:
        if "@" in p:
            continue                            # 이메일 패턴은 위에서 처리
        # 도메인 매칭: 정확히 같거나 서브도메인 (mail.notion.so ⊂ notion.so)
        if domain == p or domain.endswith("." + p):
            return True
    return False
