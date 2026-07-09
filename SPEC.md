# Spam Detector — 프로그램 명세서 (SPEC)

> **문서 목적**: 완성본 기준으로 "무엇이 작동하고, 어떻게 연결되며, 각 에이전트가 무엇을 하면 되는지"를 정리한 협업용 단일 명세.
> **대상**: Planner(백엔드)·Designer(프론트)·Reviewer(분석). 공통 규칙은 `Claude.md`, 역할은 `Agent.md` 참조.
> **갱신 주체**: Planner. 변경 시 `CHANGELOG.md`와 함께 갱신.

---

## 1. 제품 개요

**한국어 스팸 이메일 분류 데스크탑 도구.**
- 딥러닝(양방향 LSTM, 글자 단위)로 스팸/정상 판정 → 확률 → **3단계(스팸/검토/정상)**
- 판정 결과를 **MySQL**에 저장, 사용자 교정을 받아 **재학습으로 똑똑해짐**(피드백 루프)
- **트레이 상주형 메모창 스타일** 데스크탑 앱 (CustomTkinter + pystray)
- 개인용 → 로컬 DB. (다중 사용자 확장 시 서버 DB, `config.py`의 host만 교체)

---

## 2. 기능 목록 & 상태

| # | 기능 | 상태 | 담당 |
|---|------|:---:|:---:|
| 1 | 한국어 스팸/정상 분류 (LSTM, ko F1 0.968) | ✅ 완료 | Planner |
| 2 | 3단계 판정 (🔴스팸/🟡검토/🟢정상) | ✅ 백엔드 완료 | Planner |
| 3 | 이메일 필드 구조화 (제목/발신/본문/첨부) + 첨부 확장자 신호 | ✅ 백엔드 완료 | Planner |
| 4 | 피드백 루프 (사용자 교정 → 재학습 반영) | ✅ 완료 | Planner |
| 5 | MySQL 저장/조회/통계/학습이력 | ✅ 완료 | Planner |
| 6 | EDA 노트북 (전처리·시각화) | ✅ 완료 | Planner |
| 7 | 데스크탑 앱 (트레이 상주) | 🚧 진행중 | Designer |
| 8 | **3단계·4필드 UI 연동** | ⬜ 예정 | Designer |
| 9 | **Gmail 연동** (가져오기→판정→저장, 하이브리드) | ⬜ 예정 | Planner+Designer |
| 10 | 영어 전용 모델 (단어 단위) | ⬜ 보류 | Planner |

---

## 3. 아키텍처 / 데이터 흐름

```
[입력]                        [백엔드/모델]                 [저장/피드백]
수동 입력(제목/발신/본문/첨부) ─┐
                              ├─► compose_email() ─► SpamPredictor ─► (tier, prob)
Gmail 가져오기(예정) ──────────┘        (글자단위 LSTM)         │
                                                              ├─► DB: messages 저장
                                                              │
[앱 표시] 🔴/🟡/🟢 + 확률, 최근목록, 통계 ◄───────────────────┘
      │
      └─ 사용자 교정 [🚫스팸/✅정상] ─► DB: user_reports
                                              │
[재학습] train.py ◄── user_reports 를 학습셋에 포함(×5) ── "쓸수록 똑똑해짐"
```

**학습 파이프라인**: `make_seed_data.py`(합성 생성) → `build_dataset.py`(실+합성 병합 → `data/spam.csv`) → `train.py`(학습+평가+DB기록, user_reports 포함).

---

## 4. 모듈 맵 (파일별 역할)

| 파일 | 역할 | 담당 |
|-----|------|:---:|
| `src/preprocessing.py` | 글자단위 토큰화, 어휘사전, `compose_email()` | Planner |
| `src/model.py` | 양방향 LSTM + 평균풀링 | Planner |
| `src/build_dataset.py` | 실+합성 데이터 병합 (한국어 전용 현재) | Planner |
| `src/make_seed_data.py` | 합성 이메일 생성 (첨부·링크 편향방지 포함) | Planner |
| `src/train.py` | 학습·언어별평가·피드백반영·DB기록 | Planner |
| `src/predict.py` | 추론 (`SpamPredictor`) — 아래 API | Planner |
| `src/database.py` | MySQL 연동 함수 | Planner |
| `src/init_db.py` | 스키마 적용 | Planner |
| `app/app.py` | 데스크탑 앱 (트레이 상주 UI) | **Designer** |
| `config/config.py` | 경로·DB접속·임계값 (gitignore) | Planner |
| `notebooks/01_eda_preprocessing.ipynb` | EDA·시각화 | Planner |

---

## 5. 백엔드 API 계약 (Designer 연동용) ⭐

프론트는 아래만 호출하면 됩니다. **시그니처·반환값 고정** (Planner가 유지).

### 판정 — `from src.predict import SpamPredictor`
```python
predictor = SpamPredictor()   # 모델 없으면 SystemExit -> 학습 안내 필요

# 3단계 + 필드 입력 (권장)
tier, prob = predictor.predict_email_tier(subject="", sender="", body="", attachment="")
#   tier: 'spam' | 'review' | 'ham'   (🔴 / 🟡 / 🟢)
#   prob: 0.0 ~ 1.0 (스팸 확률)

# 3단계 + 단일 텍스트
tier, prob = predictor.predict_tier(text)

# 이진 판정 (하위호환)
label, prob = predictor.predict(text)                 # label: 'spam'|'ham'
label, prob = predictor.predict_email(subject, sender, body, attachment)
```

### DB — `from src import database`
```python
database.save_prediction(content, predicted_label, spam_prob,
                         sender=None, source='manual', model_version='v1')
database.save_report(content, user_label, note=None)   # user_label: 'spam'|'ham' (피드백)
database.fetch_recent(limit=20)   # -> list[dict]: created_at, predicted_label, spam_prob, content ...
database.fetch_stats()            # -> dict: total, spam_count, ham_count
database.count_reports()          # -> dict: total, spam_count, ham_count
database.fetch_reports(limit=20)  # -> list[dict]
```
> DB 미연결 시 함수는 예외 발생 → UI에서 try/except로 "MySQL 확인" 안내 권장.

### 색상 매핑 (UI 가이드)
| tier | 표시 | 색(참고) |
|-----|------|------|
| `spam` | 🔴 스팸 | 빨강 |
| `review` | 🟡 검토 필요 | 노랑 |
| `ham` | 🟢 정상 | 초록 |

---

## 6. DB 스키마 (`config/db_schema.sql`)

- `messages` : 판정 결과 (source, sender, content, predicted_label, spam_prob, model_version, created_at)
- `training_runs` : 학습 성능 이력 (accuracy, f1_score 등)
- `user_reports` : 사용자 교정 정답 (content, user_label, note) → 재학습에 사용

> Gmail 연동 시 `messages`에 `gmail_id` 컬럼 추가 예정 (중복 방지·조치용).

---

## 7. 설정 / 임계값 (`config/config.py`)

| 항목 | 기본값 | 의미 |
|-----|:---:|------|
| `SPAM_THRESHOLD` | 0.5 | 이진 판정 기준 |
| `REVIEW_LOW` | 0.4 | 이 미만 = 정상 |
| `SPAM_HIGH` | 0.7 | 이 이상 = 스팸, 사이 = 검토 |
| `MODEL_PATH` / `VOCAB_PATH` | models/ | 학습 산출물 |
| `DB_CONFIG` | localhost:3306 | MySQL 접속 (서버 전환 시 host만 변경) |

---

## 8. 데이터셋 구조

```
data/
├── ko/          실제 한국어 (지자체 정상 5 + 우체국 스팸)   ← 사용
├── en/          영어 (completeSpamAssassin)                ← 영어모델용 보관(현재 미사용)
├── synthetic/   korean_synth(사용) / english_synth(보관) / demo_samples(데모)
└── spam.csv     최종 병합 결과 (build 산출물, 직접 편집 금지)
```

---

## 9. 미완 / 예정

- **Gmail 연동(방안2 하이브리드)**: `gmail_service.py`(OAuth·fetch) + 파이프라인 + `messages.gmail_id`.
  안전장치 = 읽기전용 우선, 삭제/라벨은 사용자 확인 후. 사용자측 `credentials.json` 필요.
- **영어 전용 모델**: 단어 단위(TF-IDF/워드임베딩+DL). 글자단위론 영어 불가 판명. 언어감지 라우팅 필요.
- **초단문 문자체**: 이메일 분류 범위 밖(약점) — 피드백 루프로 보완 가능.

---

## 10. 에이전트별 할 일

### Designer (프론트)
- [ ] 입력 UI를 **4필드**(제목/발신자/본문/첨부)로 → `predict_email_tier()` 호출
- [ ] 결과를 **3단계 3색**(🔴/🟡/🟢 + 확률)으로 표시
- [ ] [🚫스팸]/[✅정상] 버튼 → `database.save_report()`
- [ ] (Gmail 연동 후) "📥 Gmail 가져오기" 버튼
- ⚠️ 백엔드 로직/파일은 수정 금지 (API만 호출)

### Reviewer (분석)
- [ ] API 계약(5장) 준수 여부, 예외처리(DB미연결/모델부재) 점검
- [ ] 데이터 편향(첨부=스팸, 링크=스팸, 채널) 재발 여부 분석 → 피드백
- [ ] 3단계 임계값(0.4/0.7) 적정성 검토

### Planner (백엔드)
- [x] 분류·3단계·필드·첨부·피드백·DB
- [ ] Gmail 연동 백엔드
- [ ] (보류) 영어 단어단위 모델

---

## 11. 실행 방법

```powershell
conda activate spam_detector
cd "C:\Users\Win11Pro\Documents\과제\spam_detector"
python src\build_dataset.py   # 데이터 병합
python src\train.py           # 학습 (user_reports 자동 포함)
python app\app.py             # 앱 실행
jupyter notebook notebooks\01_eda_preprocessing.ipynb   # EDA
```
