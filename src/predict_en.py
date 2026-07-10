"""
영어(단어 단위) 모델로 스팸 여부를 예측한다. 한국어 SpamPredictor와 동일한 API.

사용:
    from src.predict_en import EnglishSpamPredictor
    p = EnglishSpamPredictor()
    label, prob = p.predict("Thank you for your order, it will arrive on Monday.")
"""
import os
import sys

import torch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing_en import encode, load_vocab
from src.preprocessing import compose_email   # 필드 조합은 언어 무관, 그대로 재사용
from src.model import SpamLSTM
from config.config import (MODEL_PATH_EN, VOCAB_PATH_EN, SPAM_THRESHOLD,
                            REVIEW_LOW, SPAM_HIGH)

MAX_LEN = 300         # train_en.py 와 동일하게 유지


class EnglishSpamPredictor:
    def __init__(self, model_path=MODEL_PATH_EN, vocab_path=VOCAB_PATH_EN):
        if not (os.path.exists(model_path) and os.path.exists(vocab_path)):
            raise SystemExit(
                "영어 모델/어휘사전이 없습니다. 먼저 python src/train_en.py 를 실행하세요."
            )
        self.vocab = load_vocab(vocab_path)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = SpamLSTM(vocab_size=len(self.vocab)).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

    def predict(self, text: str):
        ids = torch.tensor([encode(text, self.vocab, MAX_LEN)],
                           dtype=torch.long).to(self.device)
        with torch.no_grad():
            prob = torch.sigmoid(self.model(ids)).item()
        label = "spam" if prob >= SPAM_THRESHOLD else "ham"
        return label, prob

    def predict_email(self, subject="", sender="", body="", attachment=""):
        text = compose_email(subject, sender, body, attachment)
        return self.predict(text)

    @staticmethod
    def to_tier(prob: float) -> str:
        if prob >= SPAM_HIGH:
            return "spam"
        if prob < REVIEW_LOW:
            return "ham"
        return "review"

    def predict_tier(self, text: str):
        _, prob = self.predict(text)
        return self.to_tier(prob), prob

    def predict_email_tier(self, subject="", sender="", body="", attachment=""):
        text = compose_email(subject, sender, body, attachment)
        return self.predict_tier(text)


if __name__ == "__main__":
    predictor = EnglishSpamPredictor()
    samples = [
        "Thank you for your order. Your package will arrive on Monday.",
        "Congratulations! You won $1000000. Click here to claim now!",
    ]
    for s in samples:
        label, prob = predictor.predict(s)
        print(f"[{label:4}] {prob:.2%}  {s}")
