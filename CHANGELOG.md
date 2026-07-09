# Changelog

## [Unreleased]

### 2026-07-09

#### Added (Planner — Gmail 연동 백엔드, 읽기전용)
- `src/gmail_service.py` : OAuth2 인증(token 캐시) + `fetch_recent(n)` — 제목/발신/본문/**첨부파일명**/gmail_id 추출(MIME 디코딩)
- `src/gmail_pipeline.py` : 가져오기 → `predict_email_tier` 판정 → DB 저장(source='gmail', gmail_id 중복 방지)
- `db_schema.sql` + `init_db.py` : `messages.gmail_id` 컬럼 + 마이그레이션(기존 테이블 자동 추가)
- `database.py` : `save_prediction(gmail_id=...)`, `existing_gmail_ids()` 추가
- `config.py` : `GMAIL_CREDENTIALS_PATH/TOKEN_PATH/FETCH_COUNT`. `.gitignore` : credentials.json/token.json 제외
- `requirements.txt` : google-api-python-client / auth-oauthlib / auth-httplib2 (설치 완료)
- 검증: import·스키마 마이그레이션 OK. **실연동 성공** — credentials.json 인증 후 실제 메일 20건 가져와 판정·저장 확인
  - 실측 관찰: 영어 메일(Notion/Roboflow/Kaggle) 전부 스팸 오판 → **영어 모델 필요성 실증**.
    일부 한국어 알림(클래스룸)은 피드백 루프로 교정 가능
- 안전: 스코프 `gmail.readonly`, 첨부파일명은 기능2(확장자 신호)와 연결
- SPEC.md 최신화: 기능상태(9a완료/9b·9c예정)·모듈맵·API·Designer 할일(가져오기 버튼) 반영

#### Added (Planner — 협업 명세서)
- `SPEC.md` : 완성본 기준 기능·아키텍처·데이터흐름·**백엔드 API 계약**·DB스키마·
  데이터셋 구조·미완(Gmail/영어모델)·**에이전트별 할 일**(Designer/Reviewer/Planner) 정리
  → Designer가 API 연동, Reviewer가 분석 시 참조하는 단일 기준 문서

#### Added (Planner — 상용 기능 3: 3단계 판정)
- `config.py` : `REVIEW_LOW=0.4`, `SPAM_HIGH=0.7` 임계값 (조정 가능)
- `predict.py` : `to_tier()`, `predict_tier()`, `predict_email_tier()` — 🔴스팸/🟡검토/🟢정상
- 검증: 애매한 광고성 메일(57%)을 '검토필요'로 분리, 명확한 스팸/정상은 그대로
- ※ UI(3색 표시·4필드 입력)는 Designer 담당. 백엔드 API는 준비 완료

#### Added (Planner — 상용 기능 2: 이메일 필드 구조화 + 첨부)
- `preprocessing.py` : `compose_email(subject, sender, body, attachment)` — 평문 조합(마커 편향 방지) + 첨부 표시
- `predict.py` : `predict_email(...)` — 필드 분리 입력 지원 (기존 predict(text) 하위호환)
- `make_seed_data.py` : 합성에 첨부 추가 (정상=안전확장자 .pdf/.xlsx, 스팸=위험확장자 .exe/.html)
- `build_dataset.py` : 우체국 스팸의 **실제 첨부 컬럼** 조합 (제목+첨부)
- 검증: .pdf→스팸확률↓(0%), .exe/.html→↑(15~17%), "첨부=스팸" 편향 없음. ko F1 0.968

#### Added (Planner — 상용 기능 1: 피드백 루프)
- `train.py` : DB `user_reports`(사용자 교정)를 **학습셋에만** 추가 (테스트 누수 방지) + ×5 가중
  → 등록 → 재학습 → 반영. "쓸수록 똑똑해지는" 루프 완성
- 시연 검증: 오답(엄마 나 저녁에 도착 spam95%)을 정상 등록 → 재학습 → ham4%로 교정, 유사문장 일반화 확인

#### Changed (Planner — 한국어 전용 모델로 확정 + 데이터 재편)
- **영어 전면 재조사 → 한국어 전용으로 결정**
  - 영어 ham 소스 3종 시도(Enron / spam_or_not_spam / completeSpamAssassin) 모두 실패:
    일반 영어 ham(개인·거래 메일)을 스팸 오판. 원인은 **글자 단위 토큰화가 영어에 부적합**
  - 한국어를 고친 합성 ham 처방을 영어에도 적용했으나 실패 → **데이터가 아닌 방식 문제**임을 입증
  - 결론: 영어는 추후 **단어 단위 별도 모델**로 분리 예정. 현재 병합/데모에서 제외(코드·데이터는 보관)
- **데이터 폴더 재편**: `data/en/`, `data/ko/`, `data/synthetic/` 로 분리, Enron/가짜/중복 데이터 삭제
  - 영어 소스는 `en/completeSpamAssassin.csv` (일반 ham, Enron 0%)로 정리(향후 영어모델용)
- **한국어 합성 보강**: `make_seed_data.py`에 개인 안부/거래(배송·결제·예약) 템플릿 추가
  → 약점이던 안부·결제 정상 판정 개선 (생일축하 spam74%→ham, 신한카드 spam66%→ham)
- **링크 편향 방지**: 합성 링크를 라벨 무관 ~50% 부착 (A/B로 링크 영향 ~0p 확인)
- 한국어 전용 재학습: test Acc **0.935** / 종합 진단 9/10 (스팸 5/5, 정상 4/5)

#### Changed (Designer — 데스크탑 앱 디자인 개선)
- `app/app.py` : `sg.theme("SystemDefault")` → `LightBlue3` 테마로 교체
- 레이아웃을 `sg.Frame` 기반 카드형 섹션(현황 / 메시지 입력 / 판정 결과 / 최근 판정 결과)으로 재구성
- 주요 액션 버튼(🔍 판정 & 저장)을 강조 색상·큰 크기로 분리, 보조 버튼(등록/데모/새로고침)은 하단 행으로 정리
- 판정 결과(`-RESULT-`)에 스팸(빨강)/정상(초록)/안내(회색)/정보(파랑) 배경색 피드백 추가
- 최근 판정 테이블에 헤더 볼드체, 짝수행 배경색(`alternating_row_color`) 적용
- 기존 이벤트 키(`-CHECK-`, `-REPSPAM-`, `-REPHAM-`, `-DEMO-`, `-REFRESH-` 등)와 백엔드 로직은 변경 없음
- 실행 검증: `python main.py app` (conda env `spam_detector`) 정상 실행·정상 종료 확인

#### Changed (Designer — 트레이 상주형 "메모장" UI로 전면 전환)
- GUI 프레임워크 교체: FreeSimpleGUI(tkinter 래퍼) → **CustomTkinter + pystray**
  (네이티브 위젯 한계로 색상/레이아웃만으론 "구식" 느낌을 벗어날 수 없어 프레임워크 자체를 교체)
- `app/app.py` 전면 재작성: 실행 시 창 없이 **트레이 아이콘만 상주**, 더블클릭/메뉴 "열기"로 작은 메모창 토글
  (창 닫기(X)는 `withdraw()`로 트레이 복귀, "종료" 메뉴에서만 완전 종료)
- "최근 판정 결과" 표는 메인창에서 분리 → 트레이 메뉴 "최근 기록"의 별도 보조창(`ttk.Treeview`)으로 이동
- 보조 버튼(스팸등록/정상등록)은 아이콘 버튼으로 축소, 데모 시연/새로고침은 트레이 메뉴로 이동해 메인창을 가볍게 유지
- `requirements.txt` : `FreeSimpleGUI` → `customtkinter>=5.2`, `pystray>=0.19` 로 교체 (conda env `spam_detector`에 설치 완료)
- `README.md` : GUI 스택 설명 갱신

#### Changed (Designer — SPEC.md 반영: 4필드 입력 + 3단계 판정 UI)
- 입력을 단일 텍스트박스 → **4필드**(제목/발신자/본문/첨부)로 변경, `predictor.predict_email_tier(subject, sender, body, attachment)` 호출
- 판정 결과를 **3단계 3색**(🔴 스팸 / 🟡 검토 필요 / 🟢 정상 + 확률)으로 표시 (SPEC.md 7장 색 매핑 기준)
- 🚫/✅ 등록 버튼은 4필드를 합친 내용으로 `database.save_report()` 호출 (기존과 동일 흐름)
- ⚠️ 알아둘 점: `messages.predicted_label`이 `ENUM('ham','spam')`이라 `'review'`를 그대로 저장할 수 없음
  → DB 저장 시에는 `SPAM_THRESHOLD`(0.5) 기준 이진값으로 매핑해 저장하고, 화면 표시만 3단계로 분리
  (스키마에 `'review'`를 추가하려면 Planner/DB 쪽 변경 필요 — 이번 변경 범위 밖)
- 실행 검증: `python main.py app` (conda env `spam_detector`) 컴파일·정상 실행·정상 종료 확인

### 2026-07-08

#### Added
- 프로젝트 초기 구조 생성
  - `config/` : `config.example.py`(설정 템플릿), `db_schema.sql`(MySQL 스키마)
  - `src/` : `preprocessing.py`, `model.py`(LSTM), `train.py`, `predict.py`, `database.py`
  - `app/app.py` : 데스크탑 관리 앱 (FreeSimpleGUI)
  - `main.py` : 진입점 (train/app/test 모드)
  - `README.md`, `requirements.txt`, `.gitignore`
- Miniconda 가상환경 `spam_detector` 구축 (Python 3.11.15)
- 라이브러리 설치: torch 2.12.1(cpu), pandas 3.0.3, scikit-learn 1.9.0,
  PyMySQL, SQLAlchemy, FreeSimpleGUI

#### Notes
- 딥러닝 프레임워크는 TensorFlow 대신 **PyTorch** 사용 (Python 3.13 base 호환 이슈 회피,
  가상환경은 3.11로 구성)

#### Added (데이터셋)
- `src/make_seed_data.py` : 한국어 스팸/정상 시드 데이터 생성기 (템플릿+슬롯 조합)
- `data/spam.csv` 생성 (663건: spam 400 / ham 263)

#### Changed
- `src/preprocessing.py` : 한국어 대응 — **글자 단위** 토큰화, URL→`<url>`, 숫자→`<num>` 치환
- `src/train.py`, `src/predict.py` : `MAX_LEN` 50 → 80 (글자 단위 시퀀스 길이 대응)

#### Changed (방향 전환: 이메일 이중언어)
- 과제 방향을 SMS → **이메일 스팸 분류**로 확정 (데스크탑 앱과 정합)
- **한국어 + 영어 이중 언어** 분류로 확장 (실제 메일함 반영)
- `src/make_seed_data.py` : 이메일 형식(제목+본문, 격식체)으로 전면 교체
  → `data/korean_seed.csv` 생성 (600건, spam 300 / ham 300 균형)
- `src/build_dataset.py` 신규 : 영어(Kaggle) + 한국어 시드 병합 → `data/spam.csv`

#### Added (실데이터 통합 + 모델 개선)
- 실제 데이터 확보: 영어 Kaggle(spam_ham) + 한국어 스팸(우체국 9,025) + 한국어 정상(지자체 5개 546)
- `build_dataset.py` 재작성: 인코딩/컬럼 자동감지, 한글필터, 언어태그(본문기반), 영어 다운샘플
- `config/config.py`, `config/__init__.py` 생성 (경로는 프로젝트 루트 기준 절대경로)

#### Fixed (모델 3대 개선)
1. **패딩 washout 버그** — 마지막 은닉상태 → **패딩 제외 평균 풀링** (손실 정상 수렴)
2. **양방향 LSTM** — 영어 정확도 0.52 → 0.88 대폭 개선
3. **채널 편향(confound)** — 정상=알림톡/스팸=이메일제목 문체를 학습하던 문제 발견.
   동일 이메일 문체의 **합성 정상+스팸(korean_synth.csv)을 학습에 투입**해 완화
   → OOD 진단 2/6 수준 → 5/8, "자신만만한 오답" 제거

#### 성능 (test)
- 전체 Acc 0.927 / 한국어 0.968 / 영어 0.885 (언어별 분리 평가)

#### 데이터 역할 정리
- 학습: 실제(영·한) + 합성 한국어(채널 편향 완화)
- 데모/비교: `demo_samples.csv` (학습과 비중복, 120건)
- 미사용: emails.csv(무라벨), spam_or_not_spam.csv(ham 편중)

#### Added (EDA 노트북)
- `notebooks/01_eda_preprocessing.ipynb` : 전처리·시각화 EDA (8단계)
  - 클래스/언어 분포, 텍스트 길이 히스토그램(MAX_LEN 근거), 전처리 단계 시연,
    어휘사전·최빈토큰, 스팸/정상 특징토큰, 인코딩 예시, 예측·혼동행렬
  - 한글 폰트: Malgun Gothic. headless 실행 검증 완료(오류 0, 그래프 4)
- `requirements.txt` : matplotlib, jupyter 추가

#### Added (MySQL 연동 완료)
- MySQL Server 8.0.45 + Workbench 설치, DB `spam_detector` 생성
- `src/init_db.py` : db_schema.sql 적용 스크립트
- `db_schema.sql` : `user_reports` 테이블 추가 (사용자 스팸 등록용)
- 검증 완료: 예측→저장(messages), 통계/조회, 학습성능 기록(training_runs) 정상
- `config/config.py` : 실제 접속정보 입력 (password 문자열화, .gitignore로 커밋 제외)

#### Added (데스크탑 앱 완성)
- `app/app.py` 완성: 판정&저장 + 최근목록/통계 + 🚫스팸/✅정상 등록 + 📊데모 시연
- `database.py` : `save_report`, `fetch_reports`, `count_reports` 추가 (user_reports 연동)
- 스모크 테스트 통과 (import/통계/데모/등록 정상, 데모 120건 100%)

#### Fixed (링크 편향)
- 문제: 합성 스팸은 거의 링크 有 / 합성 정상은 링크 無 → 모델이 `<url>`을 과대평가
  (정상 메일에 링크 있으면 스팸 오판)
- 해결: `make_seed_data.py` — 템플릿에서 {링크} 제거, 라벨과 무관하게 ~50% 랜덤 부착
- 검증(A/B): 같은 문장에 링크 추가 시 스팸확률 변화 +0.0~0.5p (거의 무영향) → 해결
- 재학습 성능: 전체 0.937 / 한국어 0.968 / 영어 0.906
- 잔여(별개): "배송" 등 특정 단어가 피싱 스팸과 겹쳐 오판 — 링크와 무관

#### TODO (선택)
- [ ] 정상 배송/알림 문장 추가로 단어 편향 완화
- [ ] 재학습에 user_reports 반영
- [ ] 나이브 베이즈 베이스라인 비교
- [ ] 모델 학습 및 평가
- [ ] 데스크탑 앱 동작 확인
