"""
저장된 모델을 불러와 새 메시지의 스팸 여부를 예측한다.

사용:
    from src.predict import SpamPredictor
    p = SpamPredictor()
    label, prob = p.predict("무료 상품 당첨! 지금 클릭")
"""
import os
import sys

import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing import encode, load_vocab, compose_email
from src.model import SpamLSTM
from config.config import MODEL_PATH, VOCAB_PATH, SPAM_THRESHOLD, REVIEW_LOW, SPAM_HIGH

MAX_LEN = 250         # train.py 와 동일하게 유지


class SpamPredictor:
    def __init__(self, model_path=MODEL_PATH, vocab_path=VOCAB_PATH):
        if not (os.path.exists(model_path) and os.path.exists(vocab_path)):
            raise SystemExit(
                "학습된 모델/어휘사전이 없습니다. 먼저 python src/train.py 를 실행하세요."
            )
        self.vocab = load_vocab(vocab_path)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SpamLSTM(vocab_size=len(self.vocab)).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    def predict(self, text: str):
        """(label, spam_prob) 반환. label 은 'spam' 또는 'ham'."""
        ids = torch.tensor([encode(text, self.vocab, MAX_LEN)],
                           dtype=torch.long).to(self.device)
        with torch.no_grad():
            prob = torch.sigmoid(self.model(ids)).item()
        label = "spam" if prob >= SPAM_THRESHOLD else "ham"
        return label, prob

    def predict_email(self, subject="", sender="", body="", attachment=""):
        """이메일 필드(제목/발신자/본문/첨부)를 받아 조합 후 예측.
        앱에서 필드가 나뉘어 입력될 때 사용. (label, prob) 반환."""
        text = compose_email(subject, sender, body, attachment)
        return self.predict(text)

    @staticmethod
    def to_tier(prob: float) -> str:
        """스팸 확률 -> 3단계. spam(>=SPAM_HIGH) / review / ham(<REVIEW_LOW)."""
        if prob >= SPAM_HIGH:
            return "spam"
        if prob < REVIEW_LOW:
            return "ham"
        return "review"

    def predict_tier(self, text: str):
        """3단계 판정: (tier, prob). tier in {'spam','review','ham'}."""
        _, prob = self.predict(text)
        return self.to_tier(prob), prob

    def predict_email_tier(self, subject="", sender="", body="", attachment=""):
        """필드 입력 -> 3단계 판정: (tier, prob)."""
        text = compose_email(subject, sender, body, attachment)
        return self.predict_tier(text)


if __name__ == "__main__":
    # 간단 테스트
    predictor = SpamPredictor()
    samples = [
        "안녕하세요 내일 회의 시간 확인 부탁드립니다",
        "축하합니다 무료 상품 당첨 지금 클릭하세요",
    ]
    for s in samples:
        label, prob = predictor.predict(s)
        print(f"[{label:4}] {prob:.2%}  {s}")
