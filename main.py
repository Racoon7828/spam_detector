"""
진입점. 인자로 실행 모드 선택.

    python main.py train     # 모델 학습
    python main.py app       # 데스크탑 앱 실행
    python main.py test      # 콘솔에서 예측 테스트
"""
import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "app"

    if mode == "train":
        from src.train import main as train_main
        train_main()
    elif mode == "app":
        from src.init_db import ensure_schema
        from src.logger_config import get_logger
        try:
            ensure_schema()   # 최초 실행 시 스키마 자동 생성(멱등) — 배포판에서 init_db.py 수동 실행 불필요
        except Exception as e:
            get_logger(__name__).warning(
                f"DB 자동 초기화 실패(DB 없이도 판정 자체는 가능): {e}"
            )
        from app.app import main as app_main
        app_main()
    elif mode == "test":
        from src.predict import SpamPredictor
        p = SpamPredictor()
        text = input("메시지 입력: ")
        label, prob = p.predict(text)
        print(f"[{label}] 스팸 확률 {prob:.1%}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
