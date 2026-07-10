"""model_rollback.py 단위 테스트. 실제 모델 파일은 건드리지 않고 tmp_path + monkeypatch로 격리."""
import time

import pytest

from src import model_rollback as mr


@pytest.fixture
def fake_models(tmp_path, monkeypatch):
    """가짜 모델/어휘사전 파일 + 격리된 백업 디렉터리로 model_rollback 모듈을 몽키패치."""
    model_path = tmp_path / "model.pt"
    vocab_path = tmp_path / "vocab.json"
    model_path.write_text("v1-model")
    vocab_path.write_text("v1-vocab")
    backup_dir = tmp_path / "backups"

    monkeypatch.setattr(mr, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(mr, "_LANG_PATHS", {"ko": (str(model_path), str(vocab_path))})
    monkeypatch.setattr(mr, "MAX_BACKUPS", 2)
    return model_path, vocab_path, backup_dir


def test_backup_current_creates_backup_files(fake_models):
    mr.backup_current("ko")
    assert len(mr.list_backups("ko")) == 1


def test_backup_current_noop_when_no_existing_model(tmp_path, monkeypatch):
    # 아직 학습된 모델이 없으면(최초 학습) 백업할 게 없어 조용히 넘어가야 함
    monkeypatch.setattr(mr, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(mr, "_LANG_PATHS", {"ko": (str(tmp_path / "missing.pt"),
                                                    str(tmp_path / "missing.json"))})
    mr.backup_current("ko")  # 예외 없이 그냥 넘어가야 함
    assert mr.list_backups("ko") == []


def test_prune_keeps_only_max_backups(fake_models):
    model_path, vocab_path, _ = fake_models
    for i in range(4):
        model_path.write_text(f"v{i}-model")
        mr.backup_current("ko")
        time.sleep(1.01)  # 타임스탬프(초 단위) 충돌 방지
    assert len(mr.list_backups("ko")) == 2  # MAX_BACKUPS=2


def test_restore_recovers_previous_content_and_backs_up_current(fake_models):
    model_path, vocab_path, _ = fake_models
    mr.backup_current("ko")  # v1 백업

    # "재학습"으로 내용이 바뀐 상황 시뮬레이션
    model_path.write_text("v2-model")
    vocab_path.write_text("v2-vocab")

    ts = mr.restore("ko", 0)  # 가장 최근(v1) 백업으로 복원

    assert model_path.read_text() == "v1-model"
    assert vocab_path.read_text() == "v1-vocab"
    assert isinstance(ts, str) and ts
    # 복원 직전(v2) 상태도 백업되어 있어야 함(롤백 자체를 되돌릴 수 있게)
    assert len(mr.list_backups("ko")) == 2


def test_restore_invalid_index_raises(fake_models):
    with pytest.raises(ValueError):
        mr.restore("ko", 5)  # 백업이 없는데 index 요청
