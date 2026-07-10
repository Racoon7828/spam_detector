"""한국어(글자 단위) 전처리 단위 테스트."""
from src.preprocessing import (
    clean_text, build_vocab, encode, compose_email,
    PAD_TOKEN, UNK_TOKEN, URL_TOKEN, NUM_TOKEN,
)


def test_clean_text_url_replaced():
    toks = clean_text("확인 http://bit.ly/abc 클릭")
    assert URL_TOKEN in toks


def test_clean_text_number_replaced():
    toks = clean_text("전화 01012345678")
    assert NUM_TOKEN in toks
    assert "1" not in toks  # 숫자는 개별 글자로 안 남고 <num> 로 통째 치환됨


def test_clean_text_char_level_korean():
    assert clean_text("안녕") == ["안", "녕"]


def test_clean_text_lowercases():
    assert clean_text("ABC") == ["a", "b", "c"]


def test_build_vocab_special_tokens_fixed_indices():
    vocab = build_vocab(["안녕하세요"] * 3)
    assert vocab[PAD_TOKEN] == 0
    assert vocab[UNK_TOKEN] == 1


def test_build_vocab_min_freq_excludes_rare_tokens():
    vocab = build_vocab(["가나다"], min_freq=2)  # 각 글자 1회뿐 -> min_freq=2 미달
    assert set(vocab.keys()) == {PAD_TOKEN, UNK_TOKEN}


def test_encode_pads_short_text():
    vocab = build_vocab(["안녕"] * 3)
    ids = encode("안", vocab, max_len=5)
    assert len(ids) == 5
    assert ids[-1] == vocab[PAD_TOKEN]


def test_encode_truncates_long_text():
    vocab = build_vocab(["안녕하세요"] * 3)
    ids = encode("안녕하세요반갑습니다", vocab, max_len=3)
    assert len(ids) == 3


def test_encode_unknown_char_maps_to_unk():
    vocab = build_vocab(["안녕"] * 3)
    ids = encode("Z", vocab, max_len=1)  # 학습에 없던 글자
    assert ids == [vocab[UNK_TOKEN]]


def test_compose_email_omits_empty_fields():
    text = compose_email(subject="", sender="", body="본문만 있음", attachment="")
    assert text == "본문만 있음"


def test_compose_email_includes_all_present_fields():
    text = compose_email(subject="제목", sender="a@b.com", body="본문", attachment="x.pdf")
    assert "제목" in text
    assert "a@b.com" in text
    assert "본문" in text
    assert "첨부파일 x.pdf" in text


def test_compose_email_treats_nan_string_as_empty():
    # pandas 결측치가 문자열 'nan'으로 들어오는 경우 방어 (build_dataset.py 실사용 케이스)
    text = compose_email(subject="nan", body="본문")
    assert text == "본문"
