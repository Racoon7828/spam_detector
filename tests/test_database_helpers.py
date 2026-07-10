"""database.py 의 순수 함수(DB 연결 불필요) 단위 테스트."""
from src.database import extract_email


def test_extract_email_from_display_name():
    assert extract_email("홍길동 <a@b.com>") == "a@b.com"


def test_extract_email_lowercases():
    assert extract_email("A@B.COM") == "a@b.com"


def test_extract_email_empty_input():
    assert extract_email("") == ""
    assert extract_email(None) == ""


def test_extract_email_no_match_returns_stripped_lowered_string():
    assert extract_email("  NoEmailHere  ") == "noemailhere"


def test_extract_email_multipart_domain():
    assert extract_email("Notion <team@mail.notion.so>") == "team@mail.notion.so"
