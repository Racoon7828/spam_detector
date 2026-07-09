"""
Gmail 연동 (읽기 전용).
Google Cloud에서 받은 credentials.json 으로 OAuth2 인증 후 최근 메일을 가져온다.

준비:
  1) Google Cloud Console → 프로젝트 → Gmail API 사용 설정
  2) OAuth 동의화면(External, 테스트 사용자=본인) 구성
  3) 사용자 인증정보 → OAuth 클라이언트 ID(데스크톱 앱) → credentials.json 다운로드
  4) config/credentials.json 으로 저장
  5) 첫 실행 시 브라우저 동의 → config/token.json 자동 생성

주의: 스코프는 gmail.readonly (읽기만). 삭제/라벨 없음.
"""
import os
import sys
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_FETCH_COUNT

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service():
    """인증된 Gmail API 서비스 반환. (token 캐시/갱신)"""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        raise SystemExit(
            f"Google 라이브러리 없음: {e}\n"
            "설치: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        )

    creds = None
    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GMAIL_CREDENTIALS_PATH):
                raise SystemExit(
                    "credentials.json 이 없습니다.\n"
                    "Google Cloud에서 OAuth 클라이언트(데스크톱)를 만들어 "
                    f"{GMAIL_CREDENTIALS_PATH} 에 저장하세요."
                )
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)   # 브라우저로 동의
        with open(GMAIL_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _header(headers, name):
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract(payload):
    """본문(text/plain 우선)과 첨부파일명 목록 추출."""
    body_text = ""
    attachments = []

    def walk(part):
        nonlocal body_text
        fn = part.get("filename", "")
        if fn:
            attachments.append(fn)
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if mime == "text/plain" and data and not body_text:
            body_text = base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    if not body_text:  # fallback: 최상위 body
        data = payload.get("body", {}).get("data")
        if data:
            body_text = base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
    return body_text.strip(), " ".join(attachments)


def fetch_recent(n=None):
    """최근 메일 n건을 [{gmail_id, subject, sender, body, attachment}] 로 반환."""
    n = n or GMAIL_FETCH_COUNT
    service = get_service()
    resp = service.users().messages().list(userId="me", maxResults=n).execute()
    out = []
    for m in resp.get("messages", []):
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="full").execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        body, attachments = _extract(payload)
        out.append({
            "gmail_id": m["id"],
            "subject": _header(headers, "Subject"),
            "sender": _header(headers, "From"),
            "body": body,
            "attachment": attachments,
        })
    return out


if __name__ == "__main__":
    for e in fetch_recent(5):
        print(f"[{e['sender'][:30]}] {e['subject'][:40]} | 첨부: {e['attachment']}")
