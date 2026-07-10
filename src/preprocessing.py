"""
텍스트 전처리 + 어휘사전(vocabulary) 구축. (한국어: 글자 단위 토큰화)
- URL/숫자는 특수 토큰으로 치환 (스팸 신호 보존)
- 한글/영문/숫자/일부 기호를 '글자 단위'로 분해 -> LSTM 입력용 정수 시퀀스
"""
import re
import json
from collections import Counter

PAD_TOKEN = "<pad>"   # 길이 맞추기용
UNK_TOKEN = "<unk>"   # 어휘사전에 없는 글자
URL_TOKEN = "<url>"   # 링크 (스팸의 강한 신호)
NUM_TOKEN = "<num>"   # 숫자 덩어리

# URL/링크 패턴 (http.. 또는 xxx.co.kr, bit.ly 등 도메인 형태)
_URL_RE = re.compile(r"(https?://\S+|\b\w+\.(?:com|co\.kr|kr|ly|gl|net|org)\S*)")
_NUM_RE = re.compile(r"\d+")


def compose_email(subject="", sender="", body="", attachment="") -> str:
    """이메일 필드를 하나의 학습/예측용 텍스트로 합친다.
    구조 마커(제목:/본문:)는 실데이터 필드 비대칭 때문에 편향을 유발하므로 쓰지 않고,
    평문으로 잇되 첨부만 '첨부파일 <이름>' 형태로 표시(확장자 신호 보존)."""
    parts = []
    for x in (subject, sender, body):
        if x and str(x).strip() and str(x).strip().lower() != "nan":
            parts.append(str(x).strip())
    if attachment and str(attachment).strip() and str(attachment).strip().lower() != "nan":
        parts.append(f"첨부파일 {str(attachment).strip()}")
    return " ".join(parts)


def clean_text(text: str) -> list[str]:
    """문자열 -> 글자 단위 토큰 리스트 (한국어 대응)."""
    text = text.lower()
    text = _URL_RE.sub(f" {URL_TOKEN} ", text)   # 링크 -> <url>
    text = _NUM_RE.sub(f" {NUM_TOKEN} ", text)    # 숫자 -> <num>

    tokens = []
    i = 0
    # 특수 토큰(<url>, <num>)은 통째로, 나머지는 글자 단위로 분해
    for chunk in text.split():
        if chunk in (URL_TOKEN, NUM_TOKEN):
            tokens.append(chunk)
        else:
            for ch in chunk:
                if ch.strip():          # 공백 제외
                    tokens.append(ch)   # 한 글자 = 한 토큰
    return tokens


def build_vocab(texts: list[str], min_freq: int = 2, max_size: int = 10000) -> dict:
    """학습 텍스트로 단어->인덱스 사전 생성."""
    counter = Counter()
    for t in texts:
        counter.update(clean_text(t))

    # 특수 토큰을 0, 1 로 고정
    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for word, freq in counter.most_common(max_size):
        if freq < min_freq:
            break
        vocab[word] = len(vocab)
    return vocab


def encode(text: str, vocab: dict, max_len: int = 50) -> list[int]:
    """문자열 -> 고정 길이 정수 시퀀스."""
    tokens = clean_text(text)
    ids = [vocab.get(tok, vocab[UNK_TOKEN]) for tok in tokens]

    # 자르거나(pad) 채우기
    if len(ids) < max_len:
        ids += [vocab[PAD_TOKEN]] * (max_len - len(ids))
    else:
        ids = ids[:max_len]
    return ids


def save_vocab(vocab: dict, path: str) -> None:
    """어휘사전 저장. pickle 대신 json 사용(역직렬화 시 임의 코드 실행 위험 없음 — Reviewer 지적)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)


def load_vocab(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
