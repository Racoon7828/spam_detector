"""
최종 학습 데이터셋 병합기 (실제 데이터만).
  영어(Kaggle) + 한국어 스팸(우체국) + 한국어 정상(지자체 5개)
  -> data/spam.csv  (label, text, lang)

- 인코딩(cp949/utf-8) 자동 감지
- lang 은 본문에 한글 포함 여부로 판정 ('ko'/'en')
- 영어는 다운샘플(주력=한국어, 영어=부차)
- 한국어 spam 은 한국어 ham 개수에 맞춰 샘플 (언어 내부 균형)

실행: python src/build_dataset.py
"""
import os
import sys
import re
import glob
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.preprocessing import compose_email

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)

# --- 영어(부차): completeSpamAssassin 실제, 클래스당 목표 (+합성 보강) ---
EN_PER_CLASS = 1000

_HANGUL = re.compile(r"[가-힣]")
_NOISE = re.compile(r"반송|Returned mail|Auto reply|out of the office", re.IGNORECASE)


def read_csv_any(path):
    """인코딩 자동 감지 로드. 인코딩 실패만 다음 후보로 넘어가고, 파일 없음 등
    다른 오류(FileNotFoundError 등)는 그 자리에서 바로 드러나게 함(원인 은폐 방지)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"데이터 파일이 없습니다: {path}")
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, encoding="cp949", encoding_errors="replace")


def detect_lang(text: str) -> str:
    return "ko" if _HANGUL.search(str(text)) else "en"


def clean_series(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    s = s[s.str.len() > 5]
    return s


def longest_text_col(df: pd.DataFrame) -> str:
    return max(df.columns, key=lambda c: df[c].astype(str).str.len().mean())


# ---------- 소스별 로더 ----------
def load_english():
    """영어: en/completeSpamAssassin.csv 단일 소스(SpamAssassin, 일반 메일).
    ham·spam 같은 소스라 스타일 편향 없음. Enron 계열은 사용하지 않음."""
    path = os.path.join(DATA_DIR, "en", "completeSpamAssassin.csv")
    df = read_csv_any(path)
    df = df.rename(columns={"Body": "text", "Label": "label"})
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    # Label 0=ham, 1=spam (원시 텍스트라 URL/숫자는 우리 전처리가 <url>/<num> 처리)
    df["label"] = pd.to_numeric(df["label"], errors="coerce").map({0: "ham", 1: "spam"})
    df = df.dropna(subset=["label"])
    df = df[df["text"].str.len() > 5].drop_duplicates(subset=["text"])

    # 같은 소스에서 균형 샘플 (스타일 동일 -> 편향 없음)
    ham = df[df.label == "ham"]
    spam = df[df.label == "spam"]
    n = min(EN_PER_CLASS, len(ham), len(spam))
    ham = ham.sample(n=n, random_state=42)
    spam = spam.sample(n=n, random_state=42)
    print(f"영어(completeSpamAssassin): ham={len(ham)}, spam={len(spam)}")
    return pd.concat([ham, spam])[["label", "text"]]


def load_korean_spam():
    path = os.path.join(DATA_DIR, "ko", "한국우편사업진흥원_스팸메일 수신차단 목록_20241231.csv")
    df = read_csv_any(path)
    # 컬럼 구조: 수신일자, 수신시각, 수신여부, 제목(3), 첨부  -> 제목 사용
    # 컬럼: 수신일자, 수신시각, 수신여부, 제목(3), 첨부(4)
    sub = df.iloc[:, 3].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    att = (df.iloc[:, 4].astype(str) if df.shape[1] > 4
           else pd.Series([""] * len(df), index=df.index))
    work = pd.DataFrame({"subject": sub, "attachment": att})
    work = work[work["subject"].str.len() > 5]
    work = work[~work["subject"].str.contains(_NOISE)]   # 반송/자동응답 제거
    work = work[work["subject"].str.contains(_HANGUL)]   # 한글 포함(=한국어 스팸)만
    work = work.drop_duplicates(subset=["subject"])
    # 제목 + 실제 첨부(확장자) 를 조합 -> 첨부 신호 학습
    texts = [compose_email(subject=r.subject, attachment=r.attachment)
             for r in work.itertuples(index=False)]
    print(f"한국어 spam(우체국) 한글필터·정제후 고유: {len(texts)} (첨부 조합)")
    return pd.Series(texts)


def load_korean_ham():
    files = glob.glob(os.path.join(DATA_DIR, "ko", "경기도 *.csv"))
    texts = []
    for f in files:
        df = read_csv_any(f)
        col = longest_text_col(df)
        s = clean_series(df[col])
        texts.append(s)
        print(f"  {os.path.basename(f)[:14]}... 고유 {s.nunique()}")
    allham = pd.concat(texts).drop_duplicates()
    print(f"한국어 ham(지자체) 합계 고유: {len(allham)}")
    return allham


def load_korean_synth():
    """합성 한국어 이메일(정상+스팸) — 채널 편향 완화용. 없으면 빈 프레임."""
    path = os.path.join(DATA_DIR, "synthetic", "korean_synth.csv")
    if not os.path.exists(path):
        print("(korean_synth.csv 없음 -> 합성 미포함)")
        return pd.DataFrame(columns=["label", "text"])
    df = pd.read_csv(path)[["label", "text"]]
    print(f"한국어 합성: spam={int((df.label=='spam').sum())}, "
          f"ham={int((df.label=='ham').sum())}")
    return df


def load_english_synth():
    """합성 영어 이메일(정상+스팸) — 실제 데이터에 부족한 거래/개인 메일 보강."""
    path = os.path.join(DATA_DIR, "synthetic", "english_synth.csv")
    if not os.path.exists(path):
        print("(english_synth.csv 없음 -> 영어 합성 미포함)")
        return pd.DataFrame(columns=["label", "text"])
    df = pd.read_csv(path)[["label", "text"]]
    print(f"영어 합성: spam={int((df.label=='spam').sum())}, "
          f"ham={int((df.label=='ham').sum())}")
    return df


def main():
    print("=== 소스 로드 ===")
    # 영어는 별도 '단어 단위' 모델로 추후 추가 예정 -> 지금 병합에서 제외
    # (load_english / load_english_synth 함수는 그때 재사용)
    ko_spam = load_korean_spam()
    ko_ham = load_korean_ham()
    ko_synth = load_korean_synth()

    # 한국어 내부 균형: spam 을 ham 개수에 맞춰 샘플
    n_ko = len(ko_ham)
    ko_spam = ko_spam.sample(n=min(n_ko, len(ko_spam)), random_state=42)
    print(f"\n한국어 실제 균형: ham={len(ko_ham)}, spam={len(ko_spam)}")

    # DataFrame 조립 (실제 한국어)
    rows = []
    for t in ko_ham:
        rows.append(("ham", t))
    for t in ko_spam:
        rows.append(("spam", t))
    ko_df = pd.DataFrame(rows, columns=["label", "text"])

    # 한국어 전용: 실제(지자체 ham + 우체국 spam) + 합성 한국어
    merged = pd.concat([ko_df, ko_synth], ignore_index=True)
    merged = merged.dropna(subset=["text"])
    merged["text"] = merged["text"].astype(str).str.strip()
    merged = merged[merged["text"].str.len() > 0]
    merged = merged.drop_duplicates(subset=["text"])
    merged["lang"] = merged["text"].map(detect_lang)   # 본문 기반 언어 판정
    merged = merged.sample(frac=1, random_state=42).reset_index(drop=True)

    out = os.path.join(DATA_DIR, "spam.csv")
    merged.to_csv(out, index=False, encoding="utf-8-sig")

    print("\n=== 최종 병합 완료 ===")
    print(out)
    print("총:", len(merged))
    print(merged.groupby(["lang", "label"]).size().to_string())


if __name__ == "__main__":
    main()
