"""
스팸 분류 LSTM 학습 스크립트 (한국어 주력 / 영어 부차).

데이터셋 형식 (data/spam.csv):
    label,text,lang
    ham,제목: 회의 일정 안내 ...,ko
    spam,Subject: free money ...,en

특징:
    - 언어×클래스 층화 분리 (test 20%)
    - 한국어(주력) 오버샘플링 -> 그래디언트 비중 확보
    - pos_weight -> 클래스 불균형 보정
    - 언어별(ko/en) 분리 평가

실행:
    python src/train.py
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing import build_vocab, encode, save_vocab
from src.model import SpamLSTM
from config.config import DATASET_PATH, MODEL_PATH, VOCAB_PATH, MODEL_VERSION

MAX_LEN = 250         # 이메일 본문이 길어 여유있게
EPOCHS = 10
BATCH_SIZE = 32
LR = 5e-4
KO_OVERSAMPLE = 1        # 실제+합성으로 한국어가 충분해져 오버샘플 불필요
FEEDBACK_OVERSAMPLE = 5  # 사용자 교정(user_reports)은 소수라 가중해서 학습


def load_dataset(path):
    if not os.path.exists(path):
        raise SystemExit(
            f"데이터셋이 없습니다: {path}\n먼저 python src/build_dataset.py 를 실행하세요."
        )
    df = pd.read_csv(path)
    if "lang" not in df.columns:
        df["lang"] = "ko"
    df = df[["label", "text", "lang"]].dropna()
    df["y"] = (df["label"].str.lower() == "spam").astype(int)
    return df


def to_tensor(texts, vocab):
    seqs = [encode(t, vocab, MAX_LEN) for t in texts]
    return torch.tensor(seqs, dtype=torch.long)


def load_user_reports():
    """DB의 user_reports(사용자 등록 정답)를 학습용 DataFrame으로. 피드백 루프의 핵심.
    한국어 전용 모델이므로 한글 포함분만 사용. DB 미연결 시 빈 프레임."""
    try:
        from src.database import fetch_reports
        rows = fetch_reports(100000)
    except Exception as e:
        print(f"(user_reports 미포함: {e})")
        return pd.DataFrame(columns=["label", "text", "lang", "y"])
    if not rows:
        return pd.DataFrame(columns=["label", "text", "lang", "y"])
    df = pd.DataFrame(rows).rename(columns={"content": "text", "user_label": "label"})
    df = df[["label", "text"]].dropna()
    df = df[df["text"].astype(str).str.contains(r"[가-힣]")]   # 한국어만
    df["lang"] = "ko"
    df["y"] = (df["label"].str.lower() == "spam").astype(int)
    return df


def evaluate(model, device, texts, y, vocab, tag):
    if len(texts) == 0:
        print(f"  [{tag}] 샘플 없음")
        return None
    X = to_tensor(texts, vocab).to(device)
    with torch.no_grad():
        probs = torch.sigmoid(model(X)).cpu().numpy()
    preds = (probs >= 0.5).astype(int)
    acc = accuracy_score(y, preds)
    prec = precision_score(y, preds, zero_division=0)
    rec = recall_score(y, preds, zero_division=0)
    f1 = f1_score(y, preds, zero_division=0)
    print(f"  [{tag:8}] n={len(y):5d}  Acc={acc:.3f}  P={prec:.3f}  "
          f"R={rec:.3f}  F1={f1:.3f}")
    return dict(acc=acc, prec=prec, rec=rec, f1=f1)


def main():
    df = load_dataset(DATASET_PATH)
    print("=== 데이터 구성 ===")
    print(df.groupby(["lang", "label"]).size().to_string())

    # 층화 키: 언어 + 클래스
    strat = df["lang"] + "_" + df["label"]
    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=strat
    )

    # --- 피드백 루프: user_reports(사용자 교정)를 학습셋에만 추가 (테스트 누수 방지) ---
    reports = load_user_reports()
    if len(reports):
        train_df = pd.concat([train_df] + [reports] * FEEDBACK_OVERSAMPLE,
                             ignore_index=True)
        print(f"피드백 user_reports {len(reports)}건 ×{FEEDBACK_OVERSAMPLE} 학습 추가")

    # --- 한국어 오버샘플링 (train 만) ---
    ko_train = train_df[train_df["lang"] == "ko"]
    train_bal = pd.concat([train_df] + [ko_train] * (KO_OVERSAMPLE - 1), ignore_index=True)
    train_bal = train_bal.sample(frac=1, random_state=42).reset_index(drop=True)
    print(f"\n학습셋: 원본 {len(train_df)} -> 오버샘플 후 {len(train_bal)} "
          f"(한국어 ×{KO_OVERSAMPLE})")

    # 어휘사전은 학습 데이터로만
    vocab = build_vocab(train_bal["text"].tolist())
    print(f"어휘사전 크기: {len(vocab)}")

    Xtr = to_tensor(train_bal["text"].tolist(), vocab)
    ytr = torch.tensor(train_bal["y"].tolist(), dtype=torch.float32)

    # pos_weight = (음성/양성) 비율로 스팸을 가중
    n_pos = int(ytr.sum())
    n_neg = len(ytr) - n_pos
    pos_weight = torch.tensor([n_neg / max(n_pos, 1)], dtype=torch.float32)
    print(f"pos_weight(스팸 가중)={pos_weight.item():.2f}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SpamLSTM(vocab_size=len(vocab)).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    # --- 학습 ---
    model.train()
    for epoch in range(EPOCHS):
        perm = torch.randperm(len(Xtr))
        total = 0.0
        for i in range(0, len(Xtr), BATCH_SIZE):
            idx = perm[i:i + BATCH_SIZE]
            xb, yb = Xtr[idx].to(device), ytr[idx].to(device)
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total += loss.item()
        print(f"[Epoch {epoch+1}/{EPOCHS}] loss={total:.4f}")

    # --- 평가 (전체 + 언어별) ---
    model.eval()
    print("\n=== 평가 (test 세트) ===")
    overall = evaluate(model, device, test_df["text"].tolist(),
                       test_df["y"].tolist(), vocab, "전체")
    for lang in ("ko", "en"):
        sub = test_df[test_df["lang"] == lang]
        evaluate(model, device, sub["text"].tolist(), sub["y"].tolist(),
                 vocab, lang)

    # --- 저장 ---
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    save_vocab(vocab, VOCAB_PATH)
    print(f"\n모델 저장: {MODEL_PATH}\n어휘사전 저장: {VOCAB_PATH}")

    # --- DB 기록 (선택) ---
    try:
        from src.database import get_connection
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO training_runs
                   (model_version, train_size, test_size, accuracy,
                    precision_val, recall_val, f1_score)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (MODEL_VERSION, len(train_bal), len(test_df),
                 overall["acc"], overall["prec"], overall["rec"], overall["f1"]),
            )
        conn.commit()
        conn.close()
        print("학습 성능을 DB(training_runs)에 기록했습니다.")
    except Exception as e:
        print(f"(DB 기록 생략: {e})")


if __name__ == "__main__":
    main()
