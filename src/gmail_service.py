"""
Gmail 연동 (읽기 전용).
Google Cloud에서 받은 credentials.json 으로 OAuth2 인증 후 최근 메일을 가져온다.

준비:
  1) Google Cloud Console → 프로젝트 → Gmail API 사용 설정
  2) OAuth 동의화면(External, 테스트 사용자=본인) 구성
  3) 사용자 인증정보 → OAuth 클라이언트 ID(데스크톱 앱) → credentials.json 다운로드
  4) config/credentials.json 으로 저장
  5) 첫 실행 시 브라우저 동의 → config/token.json 자동 생성

스코프: gmail.modify (읽기 + 라벨/휴지통). 영구삭제는 사용하지 않음(복구 가능한 휴지통만).
※ readonly 에서 올린 것이라, 기존 token.json 이 있으면 삭제 후 재인증 필요.
"""
import os
import sys
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_FETCH_COUNT
from src.logger_config import get_logger

logger = get_logger(__name__)

# modify = 읽기 + 라벨변경/휴지통. (영구삭제 권한 mail.google.com 은 의도적으로 미사용)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


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


BATCH_SIZE = 50   # Gmail API 배치 요청 1건당 권장 최대 건수 (호출 수를 N번 -> N/50번으로 절감)


def fetch_recent(n=None):
    """최근 메일 n건을 [{gmail_id, subject, sender, body, attachment}] 로 반환.
    n 이 500 보다 크면 Gmail 페이지를 넘겨가며(pageToken) 모은다.
    본문 조회는 건마다 개별 요청하지 않고 배치(BATCH_SIZE건씩 묶음)로 보내
    HTTP 왕복 횟수를 줄인다(Reviewer 지적, SPEC 10-1 개선항목 4)."""
    n = n or GMAIL_FETCH_COUNT
    service = get_service()

    stubs = []
    page_token = None
    while len(stubs) < n:
        resp = service.users().messages().list(
            userId="me", maxResults=min(500, n - len(stubs)),
            pageToken=page_token).execute()
        stubs.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    stubs = stubs[:n]

    responses = {}

    def _on_response(request_id, response, exception):
        if exception is not None:
            logger.error(f"Gmail 메일 조회 실패 {request_id}: {exception}")
            return
        responses[request_id] = response

    for i in range(0, len(stubs), BATCH_SIZE):
        batch = service.new_batch_http_request(callback=_on_response)
        for m in stubs[i:i + BATCH_SIZE]:
            batch.add(
                service.users().messages().get(userId="me", id=m["id"], format="full"),
                request_id=m["id"],
            )
        batch.execute()

    out = []
    for m in stubs:
        msg = responses.get(m["id"])
        if msg is None:   # 배치 내 개별 실패는 건너뜀(위에서 로깅됨)
            continue
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


def apply_action(gmail_ids, action):
    """선택된 메일에 사용자 조치 실행. (사용자 확인 후 호출할 것)
    action:
      'trash'    - 휴지통으로 이동 (복구 가능)
      'spam'     - 스팸함으로 이동 (SPAM 라벨 + 받은편지함 제거)
      'not_spam' - 스팸 아님 처리 (받은편지함 복귀 + 스팸 라벨 제거)
    반환: (성공 건수, 실패 건수)
    """
    if not gmail_ids:
        return 0, 0
    service = get_service()
    ok, fail = 0, 0
    for gid in gmail_ids:
        try:
            if action == "trash":
                service.users().messages().trash(userId="me", id=gid).execute()
            elif action == "spam":
                service.users().messages().modify(
                    userId="me", id=gid,
                    body={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]}
                ).execute()
            elif action == "not_spam":
                service.users().messages().modify(
                    userId="me", id=gid,
                    body={"addLabelIds": ["INBOX"], "removeLabelIds": ["SPAM"]}
                ).execute()
            else:
                raise ValueError(f"알 수 없는 action: {action}")
            ok += 1
        except Exception as e:
            logger.error(f"Gmail 조치 실패 {gid}: {e}")
            fail += 1
    return ok, fail


if __name__ == "__main__":
    for e in fetch_recent(5):
        print(f"[{e['sender'][:30]}] {e['subject'][:40]} | 첨부: {e['attachment']}")
