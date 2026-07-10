"""
영어 전처리 + 어휘사전(vocabulary) 구축. (영어: 단어 단위 토큰화)

한국어 모델(preprocessing.py)은 글자 단위인데, 영어는 글자 단위 토큰화가
근본적으로 부적합함이 실험으로 확인됨(일반 영어 ham을 계속 스팸 오판, 데이터를
늘려도·합성으로 보강해도 개선 안 됨). 그래서 영어는 **단어 단위**로 별도 처리.

- URL/숫자는 특수 토큰으로 치환 (스팸 신호 보존, 한국어 모델과 동일 원칙)
- 소문자화 후 단어(알파벳/숫자 덩어리) 단위로 분해
"""
import re
import json
from collections import Counter

PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"
URL_TOKEN = "<url>"
NUM_TOKEN = "<num>"

_URL_RE = re.compile(r"(https?://\S+|\b\w+\.(?:com|co\.kr|kr|ly|gl|net|org|io)\S*)")
_NUM_RE = re.compile(r"\d+")
_WORD_RE = re.compile(r"[a-z']+")   # 아포스트로피 포함 (don't, it's)


def clean_text(text: str) -> list[str]:
    """문자열 -> 단어 단위 토큰 리스트 (영어)."""
    text = text.lower()
    text = _URL_RE.sub(f" {URL_TOKEN} ", text)
    text = _NUM_RE.sub(f" {NUM_TOKEN} ", text)

    tokens = []
    for chunk in text.split():
        if chunk in (URL_TOKEN, NUM_TOKEN):
            tokens.append(chunk)
        else:
            tokens.extend(_WORD_RE.findall(chunk))
    return tokens


def build_vocab(texts: list[str], min_freq: int = 2, max_size: int = 20000) -> dict:
    """학습 텍스트로 단어->인덱스 사전 생성."""
    counter = Counter()
    for t in texts:
        counter.update(clean_text(t))

    vocab = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for word, freq in counter.most_common(max_size):
        if freq < min_freq:
            break
        vocab[word] = len(vocab)
    return vocab


def encode(text: str, vocab: dict, max_len: int = 200) -> list[int]:
    """문자열 -> 고정 길이 정수 시퀀스 (단어 단위)."""
    tokens = clean_text(text)
    ids = [vocab.get(tok, vocab[UNK_TOKEN]) for tok in tokens]
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
