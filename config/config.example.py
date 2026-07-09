"""
설정 템플릿.
이 파일을 config.py 로 복사한 뒤 실제 값을 채워 넣으세요.
(config.py 는 .gitignore 에 등록되어 비밀정보가 커밋되지 않습니다.)
"""
import os

# 프로젝트 루트 (config/ 의 상위) 기준 절대경로 -> 실행 위치와 무관하게 동작
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- MySQL 접속 정보 ---
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "여기에_비밀번호",
    "database": "spam_detector",
    "charset": "utf8mb4",
}

# --- 모델 관련 경로/설정 ---
MODEL_PATH = os.path.join(_ROOT, "models", "spam_lstm.pt")   # 학습된 모델
VOCAB_PATH = os.path.join(_ROOT, "models", "vocab.pkl")      # 어휘사전
MODEL_VERSION = "v1"

# --- 데이터셋 경로 ---
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
GMAIL_FETCH_COUNT = 20                     # 이 값 이상이면 spam 으로 판정
