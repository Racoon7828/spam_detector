"""
LSTM 기반 스팸 분류 모델 정의.
Embedding -> LSTM -> Fully Connected -> (spam 확률)
"""
import torch
import torch.nn as nn


class SpamLSTM(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        embed_dim: int = 64,
        hidden_dim: int = 128,
        num_layers: int = 1,
        pad_idx: int = 0,
    ):
        super().__init__()
        # 단어 인덱스 -> 벡터
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        # 시퀀스 학습 (양방향 -> 앞뒤 문맥 모두 반영)
        self.lstm = nn.LSTM(
            embed_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(0.3)
        # 양방향이라 hidden_dim*2 -> 1개 출력 (스팸 로짓)
        self.fc = nn.Linear(hidden_dim * 2, 1)

    def forward(self, x):
        # x: (batch, seq_len)
        mask = (x != 0).unsqueeze(-1).float()     # 패딩(0) 제외 마스크 (batch, seq, 1)
        embedded = self.embedding(x)              # (batch, seq_len, embed_dim)
        lstm_out, _ = self.lstm(embedded)         # (batch, seq_len, hidden_dim)

        # 패딩을 제외한 평균 풀링 -> 마지막 은닉상태가 패딩에 씻기는 문제 방지
        summed = (lstm_out * mask).sum(dim=1)     # (batch, hidden_dim)
        counts = mask.sum(dim=1).clamp(min=1.0)   # 실제 길이
        pooled = summed / counts                  # 평균

        out = self.dropout(pooled)
        logit = self.fc(out).squeeze(1)           # (batch,)
        return logit                               # sigmoid 는 손실함수/예측에서 적용
