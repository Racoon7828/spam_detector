"""
DB 초기화: config/db_schema.sql 을 실행해 데이터베이스와 테이블을 생성한다.

실행: python src/init_db.py
"""
import os
import sys

import pymysql

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import DB_CONFIG

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "db_schema.sql",
)


def main():
    # 스키마가 데이터베이스를 생성하므로, database 지정 없이 접속
    conf = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    try:
        conn = pymysql.connect(**conf)
    except Exception as e:
        raise SystemExit(f"MySQL 연결 실패: {e}\nconfig/config.py 의 접속정보를 확인하세요.")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        raw = f.read()

    # 주석(--) 제거 후 세미콜론 단위로 실행
    lines = [ln for ln in raw.splitlines() if not ln.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]

    with conn.cursor() as cur:
        for st in statements:
            cur.execute(st)
    conn.commit()

    # 결과 확인
    with conn.cursor() as cur:
        cur.execute("USE spam_detector")
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
    conn.close()

    print("DB 초기화 완료: spam_detector")
    print("생성된 테이블:", tables)


if __name__ == "__main__":
    main()
