"""
피드백 임계치 기반 자동 재학습 (백그라운드).

트리거: `database.save_report()` 가 호출될 때마다(사용자가 스팸/정상 피드백을 등록할 때)
        자동으로 체크됨. 언어별(한국어/영어) 새 피드백 수가 AUTO_RETRAIN_THRESHOLD 이상이면
        백그라운드 스레드로 재학습을 실행한다.

안전장치: 새로 학습한 모델의 test F1 이 기존 배포 모델보다 AUTO_RETRAIN_MAX_F1_DROP 이상
         나쁘면 모델 파일을 덮어쓰지 않고 배포를 보류한다(기존 모델 그대로 유지). 시도 자체는
         training_runs 에 `<version>-skipped` 로 기록해, 다음 카운트 기준점만 갱신되고
         곧바로 재시도가 반복되지 않게 한다.

핫 리로드: 배포 성공 시 predict_router 의 예측기 캐시를 무효화해, 실행 중인 앱이 재시작 없이
          다음 예측부터 새 모델을 즉시 사용하게 한다.

수동 실행(테스트/디버그용): python src/auto_retrain.py
"""
import os
import re
import sys
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import torch

from config.config import (
    AUTO_RETRAIN_ENABLED, AUTO_RETRAIN_THRESHOLD, AUTO_RETRAIN_MAX_F1_DROP,
    MODEL_PATH, VOCAB_PATH, MODEL_VERSION,
    MODEL_PATH_EN, VOCAB_PATH_EN, MODEL_VERSION_EN,
)
from src.logger_config import get_logger

logger = get_logger(__name__)

_HANGUL = re.compile(r"[가-힣]")
_lock = threading.Lock()   # 한 번에 하나만 재학습(동시 실행 방지)

_LANG_CONFIG = {
    "ko": dict(model_version=MODEL_VERSION, model_path=MODEL_PATH, vocab_path=VOCAB_PATH),
    "en": dict(model_version=MODEL_VERSION_EN, model_path=MODEL_PATH_EN, vocab_path=VOCAB_PATH_EN),
}


def _latest_promoted(model_version):
    """실제 배포된(정상 저장된) 최근 학습 기록 — F1 비교 기준선."""
    from src.database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f1_score, trained_at FROM training_runs "
                "WHERE model_version=%s ORDER BY trained_at DESC LIMIT 1",
                (model_version,))
            return cur.fetchone()
    finally:
        conn.close()


def _latest_attempt(model_version):
    """배포 성공/보류 포함 가장 최근 시도 — 피드백 카운트 기준선(재시도 폭주 방지)."""
    from src.database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trained_at FROM training_runs "
                "WHERE model_version IN (%s, %s) ORDER BY trained_at DESC LIMIT 1",
                (model_version, model_version + "-skipped"))
            return cur.fetchone()
    finally:
        conn.close()


def _count_new_feedback(is_korean, since):
    """user_reports 중 언어(is_korean)가 맞고 since 이후 등록된 건수."""
    from src.database import fetch_reports
    rows = fetch_reports(100000)
    cnt = 0
    for r in rows:
        has_kr = bool(_HANGUL.search(str(r.get("content") or "")))
        if has_kr != is_korean:
            continue
        if since is not None and r["created_at"] <= since:
            continue
        cnt += 1
    return cnt


def _log_run(model_version, train_size, test_size, metrics):
    from src.database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO training_runs
                   (model_version, train_size, test_size, accuracy,
                    precision_val, recall_val, f1_score)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (model_version, train_size, test_size,
                 metrics["acc"], metrics["prec"], metrics["rec"], metrics["f1"]))
        conn.commit()
    finally:
        conn.close()


def _maybe_retrain_lang(lang):
    """lang: 'ko' | 'en'. 임계치 넘으면 재학습·평가 후 안전하면 배포. 반환: 상태 문자열 또는 None."""
    cfg = _LANG_CONFIG[lang]
    is_korean = (lang == "ko")

    attempt = _latest_attempt(cfg["model_version"])
    since = attempt["trained_at"] if attempt else None
    new_count = _count_new_feedback(is_korean, since)
    if new_count < AUTO_RETRAIN_THRESHOLD:
        return None

    logger.info(f"{lang}: 새 피드백 {new_count}건 >= 임계치 {AUTO_RETRAIN_THRESHOLD} -> 재학습 시작")

    if lang == "ko":
        from src.train import run_training
        from src.preprocessing import save_vocab
    else:
        from src.train_en import run_training
        from src.preprocessing_en import save_vocab

    model, vocab, metrics, train_size, test_size = run_training()

    promoted = _latest_promoted(cfg["model_version"])
    old_f1 = promoted["f1_score"] if promoted else -1.0

    if metrics["f1"] >= old_f1 - AUTO_RETRAIN_MAX_F1_DROP:
        from src.model_rollback import backup_current
        backup_current(lang)   # 교체되기 전 기존 모델을 백업(롤백 가능하게)

        os.makedirs(os.path.dirname(cfg["model_path"]), exist_ok=True)
        torch.save(model.state_dict(), cfg["model_path"])
        save_vocab(vocab, cfg["vocab_path"])
        _log_run(cfg["model_version"], train_size, test_size, metrics)

        from src.predict_router import reload_ko, reload_en
        (reload_ko if lang == "ko" else reload_en)()

        logger.info(f"{lang}: 배포 완료 (F1 {metrics['f1']:.3f}, 이전 {old_f1:.3f}) — 핫 리로드 적용됨")
        return "promoted"
    else:
        _log_run(cfg["model_version"] + "-skipped", train_size, test_size, metrics)
        logger.warning(f"{lang}: 성능 하락 감지(F1 {metrics['f1']:.3f} < "
                       f"{old_f1:.3f}-{AUTO_RETRAIN_MAX_F1_DROP}) -> 배포 보류, 기존 모델 유지")
        return "skipped_regression"


def check_and_retrain_async():
    """임계치 체크 + 필요시 백그라운드 스레드로 재학습·배포. save_report() 에서 호출됨.
    호출 즉시 반환(블로킹 없음). AUTO_RETRAIN_ENABLED=False 면 아무 것도 안 함."""
    if not AUTO_RETRAIN_ENABLED:
        return

    def _worker():
        with _lock:
            for lang in ("ko", "en"):
                try:
                    _maybe_retrain_lang(lang)
                except Exception as e:
                    logger.error(f"{lang} 재학습 실패: {e}")

    threading.Thread(target=_worker, daemon=True).start()


if __name__ == "__main__":
    # 수동 확인용: 즉시 동기 실행(임계치 이상이면 재학습, 아니면 아무 메시지 없음)
    for _lang in ("ko", "en"):
        result = _maybe_retrain_lang(_lang)
        if result is None:
            print(f"[auto_retrain] {_lang}: 새 피드백이 임계치 미만 — 재학습 안 함")
