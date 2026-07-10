"""
영어 학습 데이터셋 병합기 (단어 단위 모델용).
  실제(completeSpamAssassin) + 합성(english_synth, 거래/개인 메일 보강)
  -> data/spam_en.csv (label, text)

기존 build_dataset.py 의 load_english()/load_english_synth() 를 그대로 재사용.

실행: python src/build_dataset_en.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from src.build_dataset import load_english, load_english_synth, DATA_DIR


def main():
    print("=== 영어 소스 로드 ===")
    real = load_english()
    synth = load_english_synth()

    merged = pd.concat([real, synth], ignore_index=True)
    merged = merged.dropna(subset=["text"])
    merged["text"] = merged["text"].astype(str).str.strip()
    merged = merged[merged["text"].str.len() > 0]
    merged = merged.drop_duplicates(subset=["text"])
    merged = merged.sample(frac=1, random_state=42).reset_index(drop=True)

    out = os.path.join(DATA_DIR, "spam_en.csv")
    merged.to_csv(out, index=False, encoding="utf-8-sig")

    print("\n=== 영어 병합 완료 ===")
    print(out)
    print("총:", len(merged))
    print(merged.groupby("label").size().to_string())


if __name__ == "__main__":
    main()
