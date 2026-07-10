"""
설정 템플릿.
이 파일을 config.py 로 복사한 뒤 실제 값을 채워 넣으세요.
(config.py 는 .gitignore 에 등록되어 비밀정보가 커밋되지 않습니다.)
"""
import os

# 프로젝트 루트 (config/ 의 상위) 기준 절대경로 -> 실행 위치와 무관하게 동작
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- MySQL 접속 정보 ---
# root 대신 spam_detector 스키마 전용 최소권한 계정 권장(블레스트 반경 축소):
#   CREATE USER 'spam_app'@'localhost' IDENTIFIED BY '강한비밀번호';
#   GRANT ALL PRIVILEGES ON spam_detector.* TO 'spam_app'@'localhost';
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "spam_app",
    "password": "여기에_비밀번호",
    "database": "spam_detector",
    "charset": "utf8mb4",
}

# --- 모델 관련 경로/설정 (한국어, 글자 단위) ---
MODEL_PATH = os.path.join(_ROOT, "models", "spam_lstm.pt")    # 학습된 모델
VOCAB_PATH = os.path.join(_ROOT, "models", "vocab.json")      # 어휘사전 (json, pickle 역직렬화 위험 회피)
MODEL_VERSION = "v1"

# --- 영어 모델 경로/설정 (단어 단위, 별도 모델) ---
MODEL_PATH_EN = os.path.join(_ROOT, "models", "spam_lstm_en.pt")
VOCAB_PATH_EN = os.path.join(_ROOT, "models", "vocab_en.json")
MODEL_VERSION_EN = "en-v1"
DATASET_PATH_EN = os.path.join(_ROOT, "data", "spam_en.csv")

# --- 데이터셋 경로 (한국어) ---
DATASET_PATH = os.path.join(_ROOT, "data", "spam.csv")                 # 학습용 CSV
DEMO_PATH = os.path.join(_ROOT, "data", "synthetic", "demo_samples.csv")  # 데모(학습 미사용)

# --- 스팸 판정 임계값 ---
SPAM_THRESHOLD = 0.5   # 이진 판정(predict) 기준

# --- 3단계 판정 임계값 (predict_tier) ---
REVIEW_LOW = 0.4       # 이 미만 = 정상(ham)
SPAM_HIGH = 0.7        # 이 이상 = 스팸(spam), 사이 = 검토 필요(review)

# --- Gmail 연동 (읽기 전용) ---
# Google Cloud Console에서 OAuth 클라이언트(데스크톱) 만들어 credentials.json 을 config/ 에 넣으세요.
GMAIL_CREDENTIALS_PATH = os.path.join(_ROOT, "config", "credentials.json")
GMAIL_TOKEN_PATH = os.path.join(_ROOT, "config", "token.json")   # 첫 인증 후 자동 생성
GMAIL_FETCH_COUNT = 100   # 가져올 메일 수 (많을수록 느려짐)
GMAIL_PAGE_SIZE = 10      # 목록 한 페이지 표시 개수

# --- 자동 재학습 (피드백 임계치 기반) ---
AUTO_RETRAIN_ENABLED = True       # False 로 두면 완전히 꺼짐(수동 python src/train.py 만 사용)
AUTO_RETRAIN_THRESHOLD = 5        # 언어별 새 피드백이 이 개수 이상 쌓이면 자동 재학습
AUTO_RETRAIN_MAX_F1_DROP = 0.02   # 새 모델 F1 이 기존보다 이 폭 넘게 나쁘면 배포 보류(기존 모델 유지)
