"""
Gmail 파이프라인: 최근 메일 가져오기 → 3단계 판정 → MySQL 저장.
- gmail_id 로 이미 저장된 메일은 건너뜀 (중복 방지)
- messages.predicted_label 은 ENUM('ham','review','spam') — 3단계 판정을 그대로 저장
  (화면 표시와 DB 통계가 항상 일치하도록)

실행: python src/gmail_pipeline.py
앱에서: from src.gmail_pipeline import run;  saved, total = run()
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import MODEL_VERSION


def run(n=None):
    """가져오기→판정→저장. (신규 저장 건수, 가져온 총 건수) 반환.
    언어 자동감지(predict_router) -> 한국어(글자단위)/영어(단어단위) 모델로 라우팅."""
    from src.gmail_service import fetch_recent
    from src.predict_router import predict_email_tier_auto
    from src import database

    emails = fetch_recent(n)
    existing = database.existing_gmail_ids()

    saved = 0
    for e in emails:
        if e["gmail_id"] in existing:
            continue
        tier, prob, lang = predict_email_tier_auto(
            subject=e["subject"], sender=e["sender"],
            body=e["body"], attachment=e["attachment"])
        # 신뢰 발신자면 모델과 무관하게 정상 처리 (allowlist 규칙 우선)
        if database.is_trusted(e["sender"]):
            label, prob = "ham", 0.0
        else:
            label = tier   # 'ham' | 'review' | 'spam' 그대로 저장
        content = f"{e['subject']} {e['body']}".strip()[:5000]
        model_version = MODEL_VERSION if lang == "ko" else f"{MODEL_VERSION}-en"
        database.save_prediction(
            content=content, predicted_label=label, spam_prob=prob,
            sender=(e["sender"] or "")[:255], source="gmail",
            model_version=model_version, gmail_id=e["gmail_id"])
        saved += 1
    return saved, len(emails)


def mark_not_spam(gmail_ids):
    """선택 메일을 '스팸 아님'으로 처리:
      (1) 정상(ham) 피드백 등록 -> 재학습에 반영 (모델 학습)
      (2) Gmail 에서 스팸 아님 처리 (스팸함이면 받은편지함 복귀)
    반환: (피드백 등록 건수, Gmail 처리 성공 건수)
    """
    from src import database
    from src.gmail_service import apply_action

    reported = 0
    for gid in gmail_ids:
        content = database.get_content_by_gmail_id(gid)
        if content:
            # 벌크 처리라 매 건마다 재학습 체크(스레드+전체조회)를 트리거하지 않음 -> 루프 후 1회만
            database.save_report(content, "ham", note="gmail_not_spam", trigger_retrain=False)
            reported += 1
    if reported:
        database.trigger_retrain_check()
    ok, _ = apply_action(gmail_ids, "not_spam")
    return reported, ok


if __name__ == "__main__":
    s, t = run()
    print(f"Gmail 가져온 {t}건 중 신규 {s}건 저장 완료")
