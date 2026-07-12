# 📧 Spam Detector

딥러닝(양방향 LSTM) 기반 **한국어·영어 이중 언어** 이메일 스팸 분류기.
스팸/검토/정상 **3단계**로 판정하고, 결과를 **MySQL**에 저장해 사용자 피드백으로 **자동 재학습**된다.
가벼운 **트레이 상주형 데스크탑 앱**으로 켜두고 쓰며, **Gmail 연동**(읽기 전용)도 지원한다.

## 주요 기능
- **한/영 자동 감지 + 언어별 전용 모델**: 한국어는 글자 단위(F1 0.968), 영어는 단어 단위(F1 0.957)로 각각 학습, `predict_router`가 자동 라우팅
- **3단계 판정**: 스팸 / 검토 필요 / 정상 (임계값 `config.py`에서 조정)
- **MySQL 저장 + 사용자 피드백 재학습**: 오탐/미탐을 직접 교정 등록 → 피드백이 일정 건수 쌓이면 **자동 재학습 + 성능하락 안전장치 + 핫 리로드**(앱 재시작 불필요)
- **모델 롤백**: 배포된 모델이 이전보다 나빠 보이면 최근 백업으로 즉시 복원 가능
- **Gmail 연동(읽기 전용)**: 최근 메일을 배치 조회해 스팸/검토 메일함 관리, 신뢰 발신자(allowlist) 등록
- **트레이 상주형 데스크탑 앱**: CustomTkinter + pystray
- **로깅**: 백그라운드 작업(자동재학습, Gmail 조치 등)은 `spam_detector.log`에 기록
- **테스트**: 핵심 로직에 대한 pytest 단위 테스트 44건
- **배포용 실행파일**: PyInstaller로 패키징 가능, 배포판은 **MySQL 설치 없이 SQLite로 자동 동작**

## 기술 스택
- **언어**: Python (conda env, 3.11)
- **딥러닝**: PyTorch (양방향 LSTM + 마스킹 평균풀링)
- **DB**: 개발 환경 = **MySQL** / 배포용 실행파일 = **SQLite**(자동 전환, 설치 불필요)
- **GUI**: CustomTkinter + pystray (시스템 트레이 상주형 메모창 스타일)
- **Gmail**: google-api-python-client (OAuth2, `gmail.modify` 스코프)
- **테스트**: pytest
- **패키징**: PyInstaller (onedir)

## 프로젝트 구조
```
spam_detector/
├── config/
│   ├── config.example.py     # 설정 템플릿 (복사해서 config.py 로 사용)
│   ├── db_schema.sql         # MySQL 스키마 (개발 환경)
│   └── db_schema_sqlite.sql  # SQLite 스키마 (배포용 exe 전용)
├── src/
│   ├── database.py           # DB 연결/저장/조회 (MySQL·SQLite 백엔드 자동 전환)
│   ├── init_db.py             # 스키마 자동 생성/마이그레이션 (앱 시작 시 자동 호출)
│   ├── preprocessing.py / preprocessing_en.py   # 한/영 전처리 + 어휘사전
│   ├── model.py               # 양방향 LSTM 모델 정의
│   ├── train.py / train_en.py # 한/영 모델 학습 스크립트
│   ├── predict.py / predict_en.py / predict_router.py   # 예측 (언어 자동 라우팅)
│   ├── auto_retrain.py        # 피드백 임계치 기반 자동 재학습
│   ├── model_rollback.py      # 모델 백업/복원
│   ├── gmail_service.py / gmail_pipeline.py   # Gmail 연동
│   └── logger_config.py       # 공통 로거
├── app/
│   └── app.py                 # 데스크탑 관리 앱
├── tests/                     # pytest 단위 테스트
├── build.spec                 # PyInstaller 빌드 스펙
├── data/                      # 학습 데이터셋 (git 제외)
├── models/                    # 학습된 모델 저장 (git 제외)
├── docs/                      # 변경 이력(CHANGELOG.md) — SPEC.md는 협업용 내부 문서라 저장소 제외
└── main.py                    # 진입점
```

## 시작하기 (개발 환경)

### 1. 가상환경 & 라이브러리
```powershell
conda create -n spam_detector python=3.11
conda activate spam_detector
python -m pip install -r requirements.txt
```

### 2. 설정 파일 준비
```powershell
copy config\config.example.py config\config.py
# config.py 를 열어 MySQL 접속 정보 입력 (root 대신 전용 최소권한 계정 권장 — 파일 내 주석 참고)
```

### 3. DB 스키마
앱을 처음 실행하면 `src/init_db.py`가 **자동으로** 스키마를 생성/점검한다(수동 실행 불필요).
직접 실행하고 싶다면:
```powershell
python src\init_db.py
```

### 4. Gmail 연동 (선택)
Google Cloud에서 OAuth 클라이언트(데스크톱)를 만들어 `config/credentials.json`으로 저장하면,
앱에서 Gmail 탭 사용 시 최초 1회 브라우저 인증 후 `config/token.json`이 자동 생성된다.

## 실행
```powershell
python src\build_dataset.py     # 데이터 병합 (최초 1회)
python main.py train            # 모델 학습 (한국어; 영어는 src\train_en.py)
python main.py app               # 데스크탑 앱 실행
python main.py test              # 콘솔에서 빠른 예측 테스트

pytest                                        # 단위 테스트 44건
python src\model_rollback.py --list ko        # 모델 백업 목록 (ko/en)
python src\model_rollback.py --restore ko 0   # 가장 최근 백업으로 복원
```

## 배포용 실행파일 만들기
```powershell
pyinstaller build.spec
```
`dist\spam_detector\spam_detector.exe`가 생성된다(onedir 모드 — 폴더째로 배포).
**대상 PC에 MySQL 설치가 필요 없다**: 배포용 exe는 자동으로 SQLite(파일 DB)를 사용하도록 전환된다.

> ⚠️ 빌드 시점의 `config/config.py`(MySQL 비밀번호 포함)가 실행파일에 그대로 컴파일되어 들어가므로,
> 개인용 배포로만 사용하고 외부에 공유하지 않는다.

**Gmail 연동은 exe만으로는 안 된다.** 판정·저장·통계 등 나머지 기능은 exe만으로 바로 동작하지만,
Gmail은 개인 Google Cloud OAuth 인증정보가 필요해서 동봉할 수 없다(동봉하면 그 자체로 정보 유출).
Gmail 기능까지 쓰려면:
1. `credentials.json`을 실행파일 옆이 아니라 **`dist\spam_detector\_internal\config\credentials.json`** 에 넣는다
   (onedir 빌드는 실제 리소스가 `_internal` 폴더 밑에 위치함)
2. 최초 1회는 인터넷 연결 + 브라우저로 OAuth 동의 필요 (이후 `token.json`이 같은 폴더에 캐시됨)
3. 검증되지 않은 OAuth 앱이라 **Google Cloud Console의 테스트 사용자로 등록된 계정만** 로그인 가능 —
   다른 사람에게 배포해 Gmail까지 쓰게 하려면 그 사람 계정을 테스트 사용자로 추가하거나, 각자 OAuth 클라이언트를 새로 만들어야 한다

`credentials.json`이 없어도 앱은 정상 실행되며, Gmail 탭을 열 때만 안내 메시지가 뜬다(다른 기능엔 영향 없음).

자세한 변경 이력은 [`docs/CHANGELOG.md`](docs/CHANGELOG.md) 참고.
