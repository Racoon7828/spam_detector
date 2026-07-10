"""
gmail_service.fetch_recent() 의 배치 조회 로직 테스트.
실제 Gmail API 호출 없이 get_service() 를 가짜 서비스로 대체해서 검증한다.
핵심 확인 사항: 배치 콜백이 완료된 순서가 뒤섞여도(네트워크 특성상 보장 안 됨)
최종 결과는 항상 원래 목록(list) 순서를 유지해야 한다.
"""
from unittest.mock import patch

from src import gmail_service


class FakeExec:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return self._data


class FakeBatch:
    """service.new_batch_http_request() 가 반환하는 가짜 배치. execute() 시
    add() 된 역순으로 콜백을 호출해 콜백 완료 순서가 섞여도 결과 순서가
    보존되는지 검증한다."""

    def __init__(self, callback, store):
        self.callback = callback
        self.store = store
        self.request_ids = []

    def add(self, request, request_id=None):
        self.request_ids.append(request_id)

    def execute(self):
        for rid in reversed(self.request_ids):
            if rid in self.store:
                self.callback(rid, self.store[rid], None)
            else:
                self.callback(rid, None, Exception("not found"))


class FakeService:
    def __init__(self, pages, store):
        self.pages = pages  # list() 호출마다 순서대로 반환할 응답들
        self.store = store
        self._list_calls = 0

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, maxResults, pageToken=None):
        data = self.pages[self._list_calls]
        self._list_calls += 1
        return FakeExec(data)

    def get(self, userId, id, format):
        # 실제 googleapiclient 처럼 요청 객체만 만들고 실행은 안 함(배치 execute()에서
        # 콜백으로 결과가 옴) -> 여기서 store 조회하면 안 됨(즉시 KeyError 발생 위험)
        return FakeExec(None)

    def new_batch_http_request(self, callback):
        return FakeBatch(callback, self.store)


def _msg(mid, subject, sender, body=""):
    return {
        "id": mid,
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
            ],
            "mimeType": "text/plain",
            "body": {},
            "parts": [],
        },
    }


def test_fetch_recent_preserves_list_order_despite_out_of_order_callbacks():
    stubs = [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]
    store = {
        "m1": _msg("m1", "제목1", "a@x.com"),
        "m2": _msg("m2", "제목2", "b@x.com"),
        "m3": _msg("m3", "제목3", "c@x.com"),
    }
    fake = FakeService(pages=[{"messages": stubs}], store=store)

    with patch.object(gmail_service, "get_service", return_value=fake):
        out = gmail_service.fetch_recent(n=3)

    assert [m["gmail_id"] for m in out] == ["m1", "m2", "m3"]
    assert out[0]["subject"] == "제목1"
    assert out[2]["sender"] == "c@x.com"


def test_fetch_recent_splits_into_multiple_batches():
    stubs = [{"id": f"m{i}"} for i in range(5)]
    store = {f"m{i}": _msg(f"m{i}", f"제목{i}", "a@x.com") for i in range(5)}
    fake = FakeService(pages=[{"messages": stubs}], store=store)

    with patch.object(gmail_service, "BATCH_SIZE", 2), \
         patch.object(gmail_service, "get_service", return_value=fake):
        out = gmail_service.fetch_recent(n=5)

    assert len(out) == 5
    assert [m["gmail_id"] for m in out] == [f"m{i}" for i in range(5)]


def test_fetch_recent_follows_pagination_until_n_reached():
    page1 = {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "TOK"}
    page2 = {"messages": [{"id": "m3"}]}
    store = {f"m{i}": _msg(f"m{i}", f"제목{i}", "a@x.com") for i in (1, 2, 3)}
    fake = FakeService(pages=[page1, page2], store=store)

    with patch.object(gmail_service, "get_service", return_value=fake):
        out = gmail_service.fetch_recent(n=3)

    assert [m["gmail_id"] for m in out] == ["m1", "m2", "m3"]


def test_fetch_recent_skips_individual_failures_without_crashing():
    stubs = [{"id": "m1"}, {"id": "m2"}]
    store = {"m1": _msg("m1", "제목1", "a@x.com")}  # m2 는 store 에 없음 -> 콜백에서 실패 처리됨
    fake = FakeService(pages=[{"messages": stubs}], store=store)

    with patch.object(gmail_service, "get_service", return_value=fake):
        out = gmail_service.fetch_recent(n=2)

    assert [m["gmail_id"] for m in out] == ["m1"]
