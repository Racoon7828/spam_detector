"""3단계 판정(to_tier) 경계값 테스트. static method 라 모델 파일 없이도 테스트 가능."""
import pytest

from src.predict import SpamPredictor
from src.predict_en import EnglishSpamPredictor
from config.config import REVIEW_LOW, SPAM_HIGH


@pytest.mark.parametrize("predictor_cls", [SpamPredictor, EnglishSpamPredictor])
def test_tier_boundaries(predictor_cls):
    # SPAM_HIGH 경계: prob >= SPAM_HIGH 는 'spam' (경계값 포함)
    assert predictor_cls.to_tier(SPAM_HIGH) == "spam"
    assert predictor_cls.to_tier(SPAM_HIGH - 0.0001) == "review"

    # REVIEW_LOW 경계: prob < REVIEW_LOW 만 'ham' (경계값 자체는 review)
    assert predictor_cls.to_tier(REVIEW_LOW) == "review"
    assert predictor_cls.to_tier(REVIEW_LOW - 0.0001) == "ham"

    # 극단값
    assert predictor_cls.to_tier(0.0) == "ham"
    assert predictor_cls.to_tier(1.0) == "spam"


@pytest.mark.parametrize("predictor_cls", [SpamPredictor, EnglishSpamPredictor])
def test_tier_mid_range_is_review(predictor_cls):
    mid = (REVIEW_LOW + SPAM_HIGH) / 2
    assert predictor_cls.to_tier(mid) == "review"
