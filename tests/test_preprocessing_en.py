"""영어(단어 단위) 전처리 단위 테스트."""
from src.preprocessing_en import (
    clean_text, build_vocab, encode,
    PAD_TOKEN, UNK_TOKEN, URL_TOKEN, NUM_TOKEN,
)


def test_clean_text_word_tokenization():
    assert clean_text("Hello World") == ["hello", "world"]


def test_clean_text_url_replaced():
    toks = clean_text("Click http://bit.ly/abc now")
    assert URL_TOKEN in toks
    assert "click" in toks and "now" in toks


def test_clean_text_number_replaced():
    toks = clean_text("Call 12345 now")
    assert NUM_TOKEN in toks


def test_clean_text_apostrophe_preserved():
    # don't/it's 같은 축약형이 단어 단위 분해에서 깨지지 않아야 함
    assert "don't" in clean_text("don't stop")


def test_build_vocab_special_tokens_fixed_indices():
    vocab = build_vocab(["hello world"] * 3)
    assert vocab[PAD_TOKEN] == 0
    assert vocab[UNK_TOKEN] == 1


def test_encode_pads_short_text():
    vocab = build_vocab(["hello world test"] * 3)
    ids = encode("hello", vocab, max_len=5)
    assert len(ids) == 5
    assert ids[-1] == vocab[PAD_TOKEN]


def test_encode_truncates_long_text():
    vocab = build_vocab(["hello world test"] * 3)
    ids = encode("hello world test extra words here", vocab, max_len=3)
    assert len(ids) == 3


def test_encode_unknown_word_maps_to_unk():
    vocab = build_vocab(["hello world"] * 3)
    ids = encode("zzznotseen", vocab, max_len=1)
    assert ids == [vocab[UNK_TOKEN]]
