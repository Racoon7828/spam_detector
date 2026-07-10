"""
공통 로깅 설정.

배경: 자동 재학습(auto_retrain.py) 등은 백그라운드 스레드에서 조용히 돌아가는데,
지금까지는 print()로만 상태를 남겨서 터미널 없이 실행(향후 exe 패키징 등)하면
아무 기록도 안 남고 사라짐. 그래서 파일에도 남는 logging으로 전환한다.

적용 범위: 백그라운드/라이브러리 성격 모듈만(auto_retrain, database, gmail_service).
train.py/build_dataset*.py 등 터미널에서 직접 실행해 진행상황을 보는 CLI 스크립트는
그대로 print() 유지(범위 밖 — 의도적).

사용:
    from src.logger_config import get_logger
    logger = get_logger(__name__)
    logger.info("...")
    logger.error("...")
"""
import logging
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(_ROOT, "spam_detector.log")

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """이름별 로거 반환. 파일(spam_detector.log) + 콘솔에 동시 기록.
    이미 핸들러가 붙어 있으면 그대로 재사용(중복 로그 방지)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(_FORMAT, _DATEFMT)

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
