"""
모델 체크포인트 백업 + 롤백.

배경: 자동재학습(auto_retrain.py)은 F1이 기존보다 많이 나쁘면 배포를 보류하지만,
"집계 F1은 괜찮은데 개별 케이스가 나빠진" 경우처럼 안전장치를 통과하고도 문제가
있을 수 있음(SPEC 7-1 문서화된 재학습 변동성 참고). 그런데 지금까지는 배포된 모델을
이전 버전으로 되돌릴 방법이 없었다(파일이 그냥 덮어써짐) — 이 모듈이 그 구멍을 메운다.

동작: 모델을 교체(배포)하기 직전에 현재(곧 교체될) 모델+어휘사전을 models/backups/ 에
복사해두고(언어별 최근 MAX_BACKUPS개만 보관), 필요하면 이전 버전으로 복원할 수 있게 한다.
복원 시에도 "복원 직전 상태"를 먼저 백업하므로 롤백 자체를 되돌리는 것도 가능하다.

사용(CLI):
    python src/model_rollback.py --list ko          # ko 백업 목록(최신순)
    python src/model_rollback.py --restore ko 0     # ko, 가장 최근 백업으로 복원
사용(코드):
    from src.model_rollback import backup_current, restore, list_backups
"""
import os
import sys
import glob
import shutil
import time
import itertools

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import MODEL_PATH, VOCAB_PATH, MODEL_PATH_EN, VOCAB_PATH_EN
from src.logger_config import get_logger

logger = get_logger(__name__)

# 초 단위 strftime만 쓰면 짧은 시간에 두 번 백업할 때(예: restore() 내부에서 복원 직전
# 백업을 뜨는 경우) 같은 타임스탬프로 파일이 충돌/덮어써질 수 있어 카운터를 덧붙여 유일하게 만듦
_id_counter = itertools.count()


def _make_backup_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S") + f"_{next(_id_counter):04d}"

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(_ROOT, "models", "backups")
MAX_BACKUPS = 3   # 언어별 보관 개수 (오래된 것부터 자동 삭제)

_LANG_PATHS = {
    "ko": (MODEL_PATH, VOCAB_PATH),
    "en": (MODEL_PATH_EN, VOCAB_PATH_EN),
}


def backup_current(lang: str):
    """현재 배포된 모델을 백업 디렉터리로 복사. 교체(덮어쓰기) 직전에 호출할 것.
    아직 학습된 모델이 없으면(최초 학습) 아무 것도 하지 않는다."""
    model_path, vocab_path = _LANG_PATHS[lang]
    if not (os.path.exists(model_path) and os.path.exists(vocab_path)):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = _make_backup_id()
    model_ext = os.path.splitext(model_path)[1]
    vocab_ext = os.path.splitext(vocab_path)[1]
    shutil.copy2(model_path, os.path.join(BACKUP_DIR, f"{lang}_{ts}_model{model_ext}"))
    shutil.copy2(vocab_path, os.path.join(BACKUP_DIR, f"{lang}_{ts}_vocab{vocab_ext}"))
    logger.info(f"모델 백업: {lang} -> {ts}")
    _prune_old(lang)


def _prune_old(lang: str):
    """언어별 MAX_BACKUPS개 초과분(오래된 것부터) 삭제."""
    models = sorted(glob.glob(os.path.join(BACKUP_DIR, f"{lang}_*_model.*")))
    if len(models) <= MAX_BACKUPS:
        return
    for old in models[:-MAX_BACKUPS]:
        ts = os.path.basename(old).split(f"{lang}_", 1)[1].split("_model")[0]
        for f in glob.glob(os.path.join(BACKUP_DIR, f"{lang}_{ts}_*")):
            os.remove(f)
        logger.info(f"오래된 백업 정리: {lang} {ts}")


def list_backups(lang: str) -> list[str]:
    """언어별 백업 타임스탬프 목록, 최신순(index 0 = 가장 최근)."""
    models = sorted(glob.glob(os.path.join(BACKUP_DIR, f"{lang}_*_model.*")), reverse=True)
    return [os.path.basename(m).split(f"{lang}_", 1)[1].split("_model")[0] for m in models]


def restore(lang: str, index: int = 0) -> str:
    """index 번째로 최근인 백업으로 복원(0=가장 최근). 복원 전 현재 상태도 백업해서
    롤백 자체를 되돌릴 수 있게 함. 핫 리로드까지 적용. 복원한 타임스탬프 문자열 반환."""
    backups = list_backups(lang)
    if index >= len(backups):
        raise ValueError(f"{lang} 백업이 {len(backups)}개뿐입니다 (index={index} 불가)")
    ts = backups[index]
    model_path, vocab_path = _LANG_PATHS[lang]
    model_ext = os.path.splitext(model_path)[1]
    vocab_ext = os.path.splitext(vocab_path)[1]

    backup_current(lang)   # 복원 전 현재 모델도 백업(되돌리기 가능하게)

    shutil.copy2(os.path.join(BACKUP_DIR, f"{lang}_{ts}_model{model_ext}"), model_path)
    shutil.copy2(os.path.join(BACKUP_DIR, f"{lang}_{ts}_vocab{vocab_ext}"), vocab_path)

    from src.predict_router import reload_ko, reload_en
    (reload_ko if lang == "ko" else reload_en)()

    logger.info(f"모델 롤백: {lang} -> {ts} 로 복원 완료, 핫 리로드 적용됨")
    return ts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="모델 체크포인트 백업 목록/복원")
    parser.add_argument("--list", choices=["ko", "en"], help="백업 목록 출력")
    parser.add_argument("--restore", nargs=2, metavar=("LANG", "INDEX"),
                        help="예: --restore ko 0 (가장 최근 백업으로 복원)")
    args = parser.parse_args()

    if args.list:
        backups = list_backups(args.list)
        if not backups:
            print(f"{args.list}: 백업 없음")
        for i, ts in enumerate(backups):
            print(f"[{i}] {ts}")
    elif args.restore:
        lang, idx = args.restore
        result_ts = restore(lang, int(idx))
        print(f"복원 완료: {lang} -> {result_ts}")
    else:
        parser.print_help()
