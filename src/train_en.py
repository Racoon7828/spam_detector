"""
영어 스팸 분류 LSTM 학습 스크립트 (단어 단위, 별도 모델).

배경: 글자 단위 토큰화(한국어 모델과 동일 방식)로는 일반 영어 이메일(개인·거래 메일)을
      계속 스팸으로 오판함이 실험으로 확인됨(Enron/spam_or_not_spam/completeSpamAssassin
      세 소스 + 합성 보강까지 시도해도 실패). 원인은 데이터가 아니라 "글자 단위가 영어에
      부적합"한 것으로 판명 -> 영어는 **단어 단위**로 별도 모델을 둔다.

데이터셋: data/spam_en.csv (build_dataset_en.py 로 생성)
실행: python src/train_en.py
"""
import os
import sys

import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.preprocessing_en import build_vocab, encode, save_vocab
from src.model import SpamLSTM
from config.config import (DATASET_PATH_EN, MODEL_PATH_EN, VOCAB_PATH_EN,
                            MODEL_VERSION_EN)

MAX_LEN = 300      # 단어 수. 중앙값 91, 75%ile 202 단어 커버
EPOCHS = 10
BATCH_SIZE = 32
LR = 5e-4
FEEDBACK_OVERSAMPLE = 5  # 사용자 교정(user_reports)은 소수라 가중해서 학습 (train.py와 동일 원칙)


def load_dataset(path):
    if not os.path.exists(path):
        raise SystemExit(
            f"데이터셋이 없습니다: {path}\n먼저 python src/build_dataset_en.py 를 실행하세요."
        )
    df = pd.read_csv(path)[["label", "text"]].dropna()
    df["y"] = (df["label"].str.lower() == "spam").astype(int)
    return df


def load_user_reports_en():
    """DB의 user_reports(사용자 교정)에서 영어 피드백만. 피드백 루프의 영어 쪽 핵심.
    train.py의 load_user_reports()는 한글 포함분만 쓰므로, 여기서는 한글이 '없는' 행만
    사용해 두 모델이 서로 겹치지 않고 각자 언어의 피드백만 반영하게 한다.
    DB 미연결 시 빈 프레임."""
    try:
        from src.database import fetch_reports
        rows = fetch_reports(100000)
    except Exception as e:
        print(f"(user_reports 미포함: {e})")
        return pd.DataFrame(columns=["label", "text", "y"])
    if not rows:
        return pd.DataFrame(columns=["label", "text", "y"])
    df = pd.DataFrame(rows).rename(columns={"content": "text", "user_label": "label"})
    df = df[["label", "text"]].dropna()
    df = df[~df["text"].astype(str).str.contains(r"[가-힣]")]   # 한글 없는 것만 (영어로 간주)
    df["y"] = (df["label"].str.lower() == "spam").astype(int)
    return df


def to_tensor(texts, vocab):
    seqs = [encode(t, vocab, MAX_LEN) for t in texts]
    return torch.tensor(seqs, dtype=torch.long)


def evaluate(model, device, texts, y, vocab, tag):
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


def run_training():
    """데이터 로드 -> 학습 -> 평가까지 수행 (저장/DB기록은 안 함).
    auto_retrain.py 가 재사용(안전장치 확인 후에만 저장하기 위해 분리).
    반환: (model, vocab, overall_metrics, train_size, test_size)"""
    df = load_dataset(DATASET_PATH_EN)
    print(f"총 {len(df)}건 (spam={df['y'].sum()}, ham={(df['y']==0).sum()})")

    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["y"]
    )

    # --- 피드백 루프: user_reports(영어) 를 학습셋에만 추가 (테스트 누수 방지) ---
    reports = load_user_reports_en()
    if len(reports):
        train_df = pd.concat([train_df] + [reports] * FEEDBACK_OVERSAMPLE,
                             ignore_index=True)
        print(f"피드백 user_reports(영어) {len(reports)}건 ×{FEEDBACK_OVERSAMPLE} 학습 추가")
    train_df = train_df.sample(frac=1, random_state=42).reset_index(drop=True)

    vocab = build_vocab(train_df["text"].tolist())
    print(f"어휘사전 크기: {len(vocab)}")

    Xtr = to_tensor(train_df["text"].tolist(), vocab)
    ytr = torch.tensor(train_df["y"].tolist(), dtype=torch.float32)

    n_pos = int(ytr.sum())
    n_neg = len(ytr) - n_pos
    pos_weight = torch.tensor([n_neg / max(n_pos, 1)], dtype=torch.float32)
    print(f"pos_weight(스팸 가중)={pos_weight.item():.2f}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SpamLSTM(vocab_size=len(vocab)).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

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

    model.eval()
    print("\n=== 평가 (test 세트) ===")
    overall = evaluate(model, device, test_df["text"].tolist(),
                       test_df["y"].tolist(), vocab, "영어")

    return model, vocab, overall, len(train_df), len(test_df)


def main():
    model, vocab, overall, train_size, test_size = run_training()

    # 교체 전 기존 모델 백업 -> 문제 있으면 model_rollback.py로 복원 가능
    from src.model_rollback import backup_current
    backup_current("en")

    os.makedirs(os.path.dirname(MODEL_PATH_EN), exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH_EN)
    save_vocab(vocab, VOCAB_PATH_EN)
    print(f"\n모델 저장: {MODEL_PATH_EN}\n어휘사전 저장: {VOCAB_PATH_EN}")

    try:
        from src.database import get_connection
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO training_runs
                   (model_version, train_size, test_size, accuracy,
                    precision_val, recall_val, f1_score)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (MODEL_VERSION_EN, train_size, test_size,
                 overall["acc"], overall["prec"], overall["rec"], overall["f1"]),
            )
        conn.commit()
        conn.close()
        print("학습 성능을 DB(training_runs)에 기록했습니다.")
    except Exception as e:
        print(f"(DB 기록 생략: {e})")


if __name__ == "__main__":
    main()
