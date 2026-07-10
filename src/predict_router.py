"""
언어별 예측기 라우터. 한국어(글자단위 SpamPredictor)와 영어(단어단위
EnglishSpamPredictor)는 완전히 다른 모델/전처리라서, 입력 언어를 보고
알맞은 예측기로 보낸다.

배경: 글자 단위 모델은 영어 일반 이메일(개인·거래 메일)을 계속 스팸 오판.
      단어 단위 영어 전용 모델을 만들어 해결(OOD 8/10, 나머지 2건도 검토 처리).

사용:
    from src.predict_router import predict_email_tier_auto
    tier, prob, lang = predict_email_tier_auto(subject, sender, body, attachment)
"""
import re

_HANGUL = re.compile(r"[가-힣]")

_ko = None
_en = None


def detect_lang(text: str) -> str:
    """본문에 한글이 있으면 'ko', 없으면 'en'."""
    return "ko" if _HANGUL.search(str(text)) else "en"


def _get_ko():
    global _ko
    if _ko is None:
        from src.predict import SpamPredictor
        _ko = SpamPredictor()
    return _ko


def _get_en():
    global _en
    if _en is None:
        from src.predict_en import EnglishSpamPredictor
        _en = EnglishSpamPredictor()
    return _en


def reload_ko():
    """한국어 예측기 캐시 무효화 -> 다음 호출 때 새로 저장된 모델 파일을 불러옴.
    자동 재학습이 새 모델을 배포한 뒤 호출(핫 리로드, 앱 재시작 불필요)."""
    global _ko
    _ko = None


def reload_en():
    """영어 예측기 캐시 무효화 (reload_ko와 동일 목적)."""
    global _en
    _en = None


def predict_email_tier_auto(subject="", sender="", body="", attachment=""):
    """이메일 필드 -> 언어 감지 -> 해당 언어 모델로 3단계 판정.
    반환: (tier, prob, lang). 특정 언어 모델이 없으면(SystemExit) 그 언어는 건너뛰고
    다른 언어 모델로 대체하지 않고 그대로 예외를 올린다(호출측에서 처리)."""
    lang = detect_lang(f"{subject} {body}")
    predictor = _get_ko() if lang == "ko" else _get_en()
    tier, prob = predictor.predict_email_tier(subject, sender, body, attachment)
    return tier, prob, lang
