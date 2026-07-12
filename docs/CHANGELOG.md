# Changelog

## [Unreleased]

### 2026-07-11 (추가) — 구조도(drawio) 최종 업데이트

#### Changed (Planner — 사용자 요청: 최종 구조 반영 + 화살표 겹침 정리)
- `docs/spam_detector.drawio` 전면 갱신 — 초기 버전(한국어 전용, MySQL만, 자동재학습/롤백/로깅/
  테스트/패키징 이전)에서 현재 최종 구조로 갱신: 언어 자동감지+라우팅, 한/영 별도 모델,
  자동재학습(F1 안전장치+model_rollback+핫리로드), 로깅, 배포용 SQLite 자동전환, 패키징,
  pytest 44건 노드 추가
- 레이아웃을 열(서빙 흐름: 입력→라우팅→전처리→모델→판정→DB→앱→Gmail조치) + 하단 두 클러스터
  (수동 학습 파이프라인 / 자동재학습 파이프라인)로 재구성하고, 좌표를 직접 계산해 **박스-박스
  겹침 0건**, 주요 간선(엣지)이 다른 박스를 관통하지 않도록 우회 경로(웨이포인트) 지정 —
  스크립트로 전수 검증(박스 겹침 검사 + 간선-박스 충돌 검사 모두 통과)

### 2026-07-11 (추가) — 배포용 exe의 MySQL 의존성 제거 (SQLite 이원화)

#### Added (Planner — 사용자 지적: 배포판을 다른 PC에 주려면 그 PC에도 MySQL 설치가 필요한 문제)
- **DB 백엔드 이원화**: `config.py`에 `DB_BACKEND = "sqlite" if sys.frozen else "mysql"` 추가 —
  개발 환경(소스 실행)은 지금까지처럼 MySQL(과제 요구사항 그대로 유지), **PyInstaller 배포용
  exe는 SQLite로 자동 전환**(파이썬 표준 내장이라 별도 설치·서버 구동 불필요, 파일 하나로 완결)
- `src/database.py`: `_SQLiteDictCursor`/`_SQLiteConnection` 래퍼 추가 — SQLite 커넥션을
  pymysql `DictCursor`와 동일한 인터페이스(딕셔너리 row, `%s` 플레이스홀더)로 감싸서 나머지
  함수는 백엔드 상관없이 그대로 동작. `TIMESTAMP` 컬럼은 커스텀 컨버터로 datetime 객체로 변환
  (MySQL과 동일하게 `app.py`의 `.strftime()` 호출과 호환). `INSERT ... ON DUPLICATE KEY
  UPDATE`(MySQL 전용 문법)는 `_upsert_trusted_sender_sql()`로 분리해 SQLite에서는
  `ON CONFLICT ... DO UPDATE`를 쓰도록 분기
- `config/db_schema_sqlite.sql` 신규 — MySQL 스키마의 SQLite 대응판(`ENUM`→`CHECK`,
  `AUTO_INCREMENT`→`INTEGER PRIMARY KEY AUTOINCREMENT`). 신규 백엔드라 기존 SQLite DB가
  없으므로 마이그레이션 로직 불필요(스키마만 적용하면 됨)
- `src/init_db.py`의 `ensure_schema()`를 `_ensure_schema_mysql()`/`_ensure_schema_sqlite()`로
  분기. SQLite 쪽은 `conn.executescript()`로 훨씬 단순(세미콜론 수동 분리 불필요)
- `build.spec`에 `config/db_schema_sqlite.sql`을 datas로 추가(배포판이 실제 참조하는 파일이므로)
- `tests/test_database_sqlite.py` 신규 6개 테스트: 스키마 생성/멱등성, `save_prediction`→
  `fetch_recent` 왕복(TIMESTAMP가 datetime으로 오는지 포함), `fetch_stats` 3단계 집계,
  신뢰 발신자 upsert(같은 pattern 재등록 시 충돌 없이 UPDATE), `gmail_id` NULL 다중 허용
  (SQLite UNIQUE 제약이 MySQL과 동일하게 여러 NULL을 허용하는지)
- **결과**: 배포된 exe는 대상 PC에 MySQL이 전혀 없어도 완전히 동작함. 개발/학습 경로는 MySQL을
  그대로 요구하므로 과제 요구사항(MySQL 활용)은 훼손되지 않음
- 검증: `pytest` 44/44 통과(기존 38 + sqlite 6), exe 재빌드 후 실행 → `spam_detector.log`에
  `DB 스키마 점검 완료(sqlite): ...` 자동 기록 확인(스모크 테스트)
- `.gitignore`에 `data/*.db` 추가
- SPEC.md 6장(DB 스키마)·10-1장("DB 배포 의존성" 항목)·모듈맵·11장(테스트 44건) 갱신

### 2026-07-11 (추가) — DB 스키마 자동 초기화

#### Added (Planner — 사용자 지적: 패키징한 exe엔 init_db.py 를 돌릴 방법이 없음)
- `src/init_db.py`: 기존 `main()`에 있던 로직을 `ensure_schema()`로 분리(멱등 — 이미 최신이면
  아무 변화 없음). 연결 실패 시 예외를 그대로 전파해 호출자가 처리 방식을 고르게 함
  (CLI `main()`은 여전히 `SystemExit`로 친절한 안내, 자동 호출 쪽은 아래처럼 경고만 남기고 계속 진행)
- `main.py`의 `app` 모드(=exe 진입점) 시작 시 `ensure_schema()` 자동 호출 추가 → 최초 배포/실행 시
  스키마가 자동 생성되어, 패키징된 배포판에서도 소스 코드로 `init_db.py`를 직접 실행할 필요가 없어짐.
  DB 연결 자체가 안 되면(MySQL 미설치 등) `logger.warning`만 남기고 앱은 정상 실행(판정은 DB 없이도
  가능하므로 앱 실행을 막지 않음)
- **한계(문서화)**: MySQL 서버 자체를 설치/동봉하는 것은 아님 — 실행 PC에 MySQL이 이미 설치되어
  구동 중이어야 하고, 이 변경은 "스키마/테이블 생성"만 자동화한 것. 다른 PC에 배포하려면 그 PC에도
  MySQL 설치 필요(SPEC 10-1 참고)
- 검증: `ensure_schema()` 직접 호출 → 기존 스키마 이미 최신 상태에서 멱등하게 통과 확인,
  `pytest` 38/38 재확인, PyInstaller 재빌드 후 exe 재실행으로 스모크 테스트
- SPEC.md 10-1장 "패키징/배포" 항목에 자동 초기화 내용 보강

### 2026-07-11

#### Added (Planner — 개선제안 1·2·3번: 로깅·테스트·모델롤백, 사용자 우선순위 승인)
- **① 로깅 체계화**: `src/logger_config.py` 신규 — `spam_detector.log` 파일 + 콘솔 동시 기록.
  적용 범위는 **백그라운드 실행 경로만**(`auto_retrain.py`, `database.py`의 자동재학습 체크,
  `gmail_service.py`의 `apply_action`) — `train.py`/`build_dataset*.py` 등 터미널에서 직접
  보는 CLI 스크립트는 진행상황 표시용 `print()` 그대로 유지(의도적 범위 제한, 전면 교체 아님)
- **③ 모델 롤백 기능**: `src/model_rollback.py` 신규
  - `backup_current(lang)`: 모델 교체 직전 현재 모델+어휘사전을 `models/backups/`에 복사,
    언어별 최근 3개만 보관(오래된 것 자동 정리)
  - `restore(lang, index)`: index번째로 최근인 백업으로 복원 + **복원 전 상태도 먼저 백업**(롤백의
    롤백 가능) + `predict_router` 핫 리로드 적용
  - 배포 경로 3곳에 통합: 자동재학습 승격 시(`auto_retrain.py`), 수동 `train.py`/`train_en.py` 저장 시
  - CLI: `python src/model_rollback.py --list ko` / `--restore ko 0`
  - 검증: 실제 파일 백업 생성 확인, 해시 비교로 복원 정확성 확인(byte-for-byte), 복원 후 핫 리로드로
    예측 정상 동작 확인
- **② 테스트 코드**: `pytest` 도입(`requirements.txt` 추가), `tests/` 5개 파일 34개 테스트
  - 전처리 한국어(글자단위)/영어(단어단위): URL/숫자 치환, 토큰화, 어휘사전, 인코딩(패딩/절단/UNK)
  - `to_tier()` 경계값(REVIEW_LOW/SPAM_HIGH 정확한 경계 포함여부, 한/영 둘 다) — 모델 파일 없이도
    테스트 가능(static method)
  - `database.extract_email()` (발신자 문자열 파싱)
  - `model_rollback` 백업/prune/복원 (tmp_path+monkeypatch로 실제 모델 파일 안 건드림)
  - **테스트가 실제 버그를 잡음**: `restore()`가 복원 직전 상태를 백업할 때 `backup_current()`를
    호출하는데, 타임스탬프가 초 단위(`%Y%m%d_%H%M%S`)라 직전 백업과 같은 초에 겹치면 파일명이
    충돌해 방금 만든 백업을 덮어써버림 → 복원해도 조용히 실패(v2가 그대로 남음). 카운터 접미사로
    타임스탬프를 유일하게 만들어 수정 → 34/34 통과
  - `pytest.ini`(testpaths=tests), `tests/conftest.py`(경로 설정)
- `.gitignore` : `models/backups/`, `.pytest_cache/` 추가
- SPEC.md : 모듈맵·11장(실행방법)·10-1장(개선제안 체크리스트) 갱신, 발견된 버그 별도 명시

#### Added (Planner — 개선제안 4·5번: Gmail API 쿼터·패키징, 이어서 진행)
- **④ Gmail API 쿼터 최적화**: `src/gmail_service.py`의 `fetch_recent()` — 메일 본문을 건마다
  개별 `messages.get()` 호출하던 것을 `service.new_batch_http_request()`로 `BATCH_SIZE=50`건씩
  묶어 HTTP 왕복 횟수 절감(예: 500건 조회 시 약 500회 → 약 11회). `format="metadata"`는 본문이
  안 와서 분류에 못 쓰므로 배치 방식 채택
  - 콜백 완료 순서가 뒤섞여도 결과는 항상 원래 `messages.list()` 순서로 재정렬(gmail id를
    `request_id`로 매핑) — 개별 메일 조회 실패는 로깅 후 건너뜀(전체 실패 아님)
  - `tests/test_gmail_service.py` 신규 4개 테스트: 순서 보존(콜백 역순 실행으로 검증)/배치 분할/
    페이지네이션/개별 실패 스킵 — 실제 Gmail API 호출 없이 가짜 서비스로 모킹
- **⑤ 패키징/배포**: `build.spec` 신규 — PyInstaller **onedir** 모드(onefile 아님)
  - onefile을 쓰지 않은 이유: onefile은 실행마다 임시폴더(MEIPASS)에 압축을 풀고 종료 시
    삭제하므로, 이 앱이 실행 중 계속 갱신해야 하는 `spam_detector.log`/재학습 결과
    `models/*.pt`/`models/backups/`/Gmail 인증캐시 `config/token.json`이 매 실행마다 사라짐.
    onedir는 `dist/spam_detector/` 폴더가 실행 간 그대로 유지되어 이 문제가 없음
  - datas: `data/img`(트레이·사이드바 아이콘), 데모 샘플, 초기 학습된 모델 4종, `db_schema.sql`
  - hiddenimports: `pystray`/`googleapiclient` 하위모듈, `PIL._tkinter_finder`, `pymysql` 등
  - `requirements.txt`에 `pyinstaller>=6.0`(빌드 전용) 추가
  - **주의(문서화)**: 빌드 시점의 `config/config.py`(DB 비밀번호 포함)가 그대로 컴파일되어
    실행파일에 들어감 — 개인용 배포로만 사용, 외부 공유 금지. `credentials.json`/`token.json`은
    동봉하지 않음(최초 실행 시 사용자가 직접 Gmail 인증)
  - 검증: `pyinstaller build.spec` 실제 빌드 성공(`dist/spam_detector/spam_detector.exe`),
    아이콘·모델·스키마 파일이 예상대로 `_internal/` 하위에 배치됨 확인, 빌드된 exe 직접 실행 →
    10초+ 크래시 없이 정상 구동 확인(스모크 테스트) 후 정리
  - `.gitignore`에 `build/`, `dist/` 추가(재생성 가능한 산출물)
- `tests/` 38개 테스트로 갱신(기존 34 + gmail_service 4)
- SPEC.md 10-1장 개선제안 4·5번 완료 처리, 모듈맵에 `build.spec` 추가

#### Fixed (Planner — DB 계정을 root → 최소권한 계정으로 교체, 사용자 승인)
- 사용자 승인("지금 만들자") 확인 후 진행. MySQL `spam_app`@`localhost` 계정 신규 생성,
  `GRANT ALL PRIVILEGES ON spam_detector.*` 만 부여(다른 스키마·서버 전체 권한 없음)
- `config/config.py`의 `DB_CONFIG`를 root → `spam_app`으로 교체 — **root 계정/비밀번호가
  이제 이 프로젝트 어디에도 저장되지 않음**(root는 MySQL Workbench 등에서 사용자가 별도 관리)
- `config/config.example.py`에도 최소권한 계정 사용 권장 + 생성 SQL 예시 추가
- 검증: 새 계정으로 `mysql.user` 등 타 스키마 접근 시도 → 거부 확인(블레스트 반경 축소 실증).
  `init_db.py`(DDL: CREATE/ALTER) 정상 동작 확인. 판정→저장→통계→피드백 전체 흐름(DML) 정상 동작 확인
- SPEC.md 10-1장 "DB 계정이 root" 항목 완료 처리

#### Fixed (Planner — 10-1 Reviewer 추가점검: 버그 2건 + 보안 2건 처리)
- **[버그] 벌크 재학습 체크 스레드 폭증**: `save_report()`에 `trigger_retrain=True/False` 파라미터 추가,
  기본은 그대로 즉시 체크(단일 등록용). `gmail_pipeline.mark_not_spam()`은 루프 중엔 `trigger_retrain=False`로
  저장만 하고, 루프 종료 후 `database.trigger_retrain_check()`를 **1회만** 호출하도록 배치화
  → N건 일괄 "스팸 아님" 처리해도 스레드/전체조회가 N배가 아니라 1회만 발생
- **[버그] `read_csv_any` 예외처리 무의미화**: `except (UnicodeDecodeError, Exception)` → `except UnicodeDecodeError`로
  좁힘 + 파일 자체가 없으면 `FileNotFoundError`를 즉시 명확히 발생(이전엔 3회 인코딩 재시도 후 뒤늦게,
  원인이 가려진 채 실패)
- **[보안] pickle → json 어휘사전**: `preprocessing.py`/`preprocessing_en.py`의 `save_vocab`/`load_vocab`을
  `pickle`(역직렬화 시 임의 코드 실행 위험) → `json`으로 전환. `config.py`/`config.example.py`의
  `VOCAB_PATH`/`VOCAB_PATH_EN` 확장자 `.pkl`→`.json`, `.gitignore`에 `models/*.json` 추가.
  형식이 바뀌어 기존 `.pkl`과 호환 안 됨 → 한/영 모델 재학습으로 `vocab.json` 재생성
- **[보안/일관성] 수동입력 길이 무제한**: `app.py` `_compose_content()`에 Gmail 경로(5000자)와 동일한
  캡 추가(`[:5000]`) — 기능 배선 1줄만 수정, Designer 스타일 코드는 그대로
- 부수 정리: `config.example.py`에 남아있던 stray 주석 조각("# 이 값 이상이면 spam 으로 판정") 제거
- 검증: 전체 `py_compile` 통과 → 한/영 모델 재학습 완료(F1 한국어 0.928, 영어 0.943 — 재학습 자연변동 범위 내,
  SPEC 7-1 기 문서화된 현상) → `predict_router`로 신규 `vocab.json`/`vocab_en.json` 로드·언어감지·판정 정상 확인
  → 옛 `vocab.pkl`/`vocab_en.pkl` 삭제(더는 안 쓰임)

#### Noted (Planner — 10-1 나머지 항목: 처리 보류, 사용자 확인 필요)
- **[버그] 영어 임계값 공유**: Reviewer도 "당장 조치 불필요"로 명시 — 10장에서 이미 데이터로 검증됨(조치 없음)
- **[보안] DB root 계정**: 실제 MySQL 계정 생성/권한변경이 필요해 **사용자 확인 후 진행 예정**(임의로 자격증명 변경 안 함)
- **[보안] Gmail 토큰 평문 저장**: OS 파일권한 문제라 코드 수정 범위 밖, 스코프 자체는 이미 안전하게 설계됨(현상 유지)
- **[개선제안 5건]**(로깅 체계화/모델 롤백/Gmail API 쿼터/테스트코드/패키징): 전부 신규 기능급 작업이라
  **임의 착수하지 않고 사용자에게 우선순위 확인 후 진행**

#### Removed (Designer — 통계 안내 문구 삭제, stale 확인)
- Planner가 `messages.predicted_label`을 `ENUM('ham','review','spam')`으로 확장해 3단계를 그대로
  저장하도록 수정(`docs/SPEC.md` 10장) → 홈 통계 카드에 있던 "통계는 이진 기준이라 검토 판정과
  다를 수 있음" 안내 문구가 더 이상 사실이 아니게 됨(이제 저장값과 화면 표시가 일치) → 문구 제거
- `on_check()`의 `db_label = tier`(Planner가 기능 배선만 수정)와 조합해 이제 통계·화면 완전 일치 확인
- 검증: `docs/SPEC.md` 재확인 후 `py_compile` 통과, 실행 중이던 프로세스 없음 확인 후 재실행

#### Fixed (Planner — Reviewer 지적 3건 처리)
- **① API 예외처리(on_check SystemExit 미방어)**: 확인해보니 **Designer가 이미 수정 완료**
  (SystemExit/Exception 방어 + DB저장실패 화면노출) — 추가 조치 불필요, 검증만 함
- **② 데이터 편향 희석 비율 실측**: `build_dataset.py`/`build_dataset_en.py`의 실제 로더 함수로 정확히 계산
  - 한국어: ham 실제546/합성640(합성 54.0%), spam 실제546/합성640(합성 54.0%) — **양 클래스 동일 비율**
    → 채널편향 방지 설계가 의도대로 작동(한쪽만 합성이 많으면 편향 재발하는데 그렇지 않음)
  - 영어: ham 실제1000/합성640(39.0%), spam 실제1000/합성305(23.4%) — 약간의 클래스간 비대칭 있으나
    OOD 8~10/10 실측으로 문제 없음 확인
  - 정직한 관찰: 두 언어 다 **합성이 절반 안팎으로 결코 적지 않음** — 효과는 검증됐지만 인지해둘 사실
- **③ 3단계 임계값(0.4/0.7) 데이터 검증**: 학습때와 동일 random_state=42 test split으로 실제 확률분포 확인
  - 한국어(n=475): true ham→(ham224/review10/spam4), true spam→(ham7/review5/spam225) — 94%가 정확한 극단
  - 영어(n=589): true ham→(ham320/review4/spam4), true spam→(ham9/review6/spam246) — 96%가 정확한 극단
  - 두 언어 모두 검토구간 1.7~3.2%로 작고 양쪽 클래스에 고르게 분산 → **현재 값 유지, 변경 근거 없음**
    (Reviewer 지적대로 "검증 안 된 고정값"이었던 건 사실이나, 검증해보니 잘 작동하는 것으로 확인)
- **④ DB 이진/3단계 불일치 — 스키마 수정**: `messages.predicted_label`을
  `ENUM('ham','spam')` → **`ENUM('ham','review','spam')`** 로 확장(`init_db.py` 마이그레이션, 실DB 적용 완료)
  - `database.py`: `save_prediction`이 3단계 그대로 받음. `fetch_stats()`에 `review_count` 추가.
    `fetch_gmail_pending`/`count_gmail_pending`의 label='spam' 필터는 `IN ('spam','review')`로 그룹핑해
    기존 Gmail 3단 토글(스팸/정상/전체)이 깨지지 않게 유지(검토 항목이 안 사라지고 스팸 탭에 포함됨)
  - `gmail_pipeline.py`: 이진 재매핑(`SPAM_THRESHOLD` 기준) 제거, `predict_email_tier_auto`의 tier를 그대로 저장
  - `app/app.py` `on_check()`: `db_label = tier`로 1줄 수정(기능 배선만, Designer 스타일 코드 안 건드림)
  - 검증: 마이그레이션 실DB 적용 → `save_prediction`으로 ham/review/spam 각각 저장 확인 →
    `fetch_stats()`가 review_count 포함해 정확히 분리 반환 확인 → **strict spam-only=51 vs
    grouped(spam+review)=52 vs API결과=52** 직접 대조로 그룹핑 로직 정확성 확인
  - ⚠️ Designer 확인 필요: 홈 통계 카드의 "통계-화면 불일치 가능" 경고 문구가 이번 수정으로 stale해짐
    (이제 일치함) → 문구 제거/갱신 권장
- SPEC.md : 6장(DB스키마)·10장(Reviewer/Planner 체크리스트) 갱신, 발견-처리 결과 전부 반영

#### Changed (Designer — 통계 안내 문구 위치를 상단으로 이동)
- 통계 카드 안내 문구를 숫자 3칸 아래 → **위쪽**으로 이동(통계를 보기 전에 이진 기준 안내를 먼저 읽도록)
- `py_compile` 확인 후 실행 중이던 프로세스 종료·재실행

#### Changed (Designer — 통계 안내 문구 디자인 재검토)
- 직전에 추가한 "검토 판정과 다를 수 있음" 안내 문구가 `wraplength` 없이 좌측정렬 긴 문장으로 들어가
  카드 폭을 넘어서거나(창 축소 시) 통계 숫자(중앙정렬)와 정렬이 어긋나 보이는 문제 → 재검토 후 수정
- `wraplength=900` 추가로 좁은 창에서도 카드 밖으로 흘러넘치지 않도록, `justify="center"` + `pack(pady=(0,12))`로
  숫자 3칸(중앙정렬)과 시각적으로 맞춰 중앙정렬, 문구도 따옴표 제거하고 더 짧게 축약
- 검증: 헤드리스로 실제 렌더된 카드폭(1195px) 대비 문구 폭(396px)이 정확히 중앙(x=399~795)에 위치,
  통계 숫자 행과 겹치지 않는 간격(17px) 확인 후 실행 중이던 구버전 프로세스 없음 확인하고 재실행

#### Fixed (Designer — Reviewer 지적사항 처리: 홈 판정 예외처리 + 저장 실패 노출)
- **버그 수정**: `on_check()`가 `predict_email_tier_auto()` 호출 시 모델 부재(`SystemExit`)를 잡지 않아
  Tkinter 콜백에서 재-raise되며 앱이 에러창 없이 조용히 종료되던 문제. `_gmail_import_worker`와 동일 패턴으로
  `SystemExit`/`Exception`을 각각 잡아 결과 칩에 안내 문구 표시 후 앱은 계속 실행되도록 수정
- **일관성 수정**: DB 저장(`save_prediction`) 실패 시 콘솔에만 출력하고 화면은 성공으로 표시되던 문제
  (`on_report()`는 이미 화면에 실패를 노출하던 것과 불일치) → 저장 실패 시 결과 칩에
  "(주의: 결과 저장 실패 - ...)" 를 판정 결과 아래 줄에 추가로 표시하도록 수정(판정 자체는 그대로 보임)
- **안내 추가**: DB는 3단계(스팸/검토/정상)를 이진(스팸/정상)으로 재매핑해 저장하므로 통계 숫자가
  화면의 "검토" 판정과 다를 수 있음 — 홈 통계 카드 하단에 안내 문구 추가
- 근거: `docs/SPEC.md` 10장 Reviewer 항목(API 계약/예외처리 점검, 3단계 임계값 검토) 중 Designer 전달 3건 처리
- 검증: `py_compile` + 헤드리스로 (1)정상 판정 (2)DB 저장 실패 모킹 → 화면에 실패 문구 노출 (3)`predict_email_tier_auto`가 `SystemExit` 발생하도록 모킹 → 앱이 죽지 않고 안내 문구만 표시되는 것 확인 후 실제 앱 재실행

#### Changed (Planner — EDA 노트북을 이중언어 구조로 전면 갱신)
- 기존 노트북은 한국어 전용/구 데이터 경로(`data/spam.csv`가 한+영 혼합이던 시절) 기준이라
  현재 구조(한국어 전용 `spam.csv` + 별도 `spam_en.csv`, `demo_samples.csv`는 `synthetic/`로 이동)와
  불일치 + 8번 셀 출력이 초기 버그 있던 모델 시절 값("회의 자료 첨부"→스팸99% 등)으로 방치돼 있었음
- 8개 섹션 전부 한국어(글자단위)/영어(단어단위) **나란히 비교**하도록 재작성:
  데이터 로드, 분포, 길이분포(글자수 MAX_LEN250 vs 단어수 MAX_LEN300), 전처리 시연,
  어휘사전(글자868/단어18497), 스팸신호토큰, 인코딩 예시, 모델예측+혼동행렬(한국어 데모셋 + 영어 held-out 8문장)
  + 언어 라우터(`predict_email_tier_auto`) 시연 셀 신규 추가
- 검증: 헤드리스 실행(nbconvert) — 코드셀 11개, 오류 0개, 그래프 5개 정상 생성.
  한국어 데모셋 정확도 1.000(n=120), 영어 held-out 정확도 1.000(n=8) 확인 후 검증 사본 삭제

#### Reviewed (Reviewer — SPEC 10장 리뷰 항목 3건 분석, 코드 수정 없음)
- **API 계약/예외처리**: `app/app.py` `on_check()`가 영어 모델 부재 시 `predict_email_tier_auto()`의
  `SystemExit`을 잡지 않아 Tkinter 콜백에서 앱이 조용히 종료되는 경로 발견(Gmail 경로는 이미 방어됨,
  동일 패턴 적용 필요). 부수로 `on_check()`의 DB 저장 실패가 화면에 노출 안 되는 비대칭 발견
  (`on_report()`는 노출) — Planner/Designer 전달
- **데이터 편향**: `make_seed_data.py`의 첨부/링크 편향 방지 설계는 의도대로 작동 확인. 실제 데이터의
  채널 편향(정상=지자체 공고문/스팸=우체국 제목목록)이 합성 데이터로 충분히 희석되는지는 실행 시점
  건수 비율 실측이 필요함을 Planner에 전달
- **3단계 임계값(0.4/0.7)**: 데이터 기반 검증 근거 없이 고정값임을 확인, test셋 확률분포 기반 재검증
  권장. DB 저장 시 이진 재매핑으로 통계-화면 표시 불일치 가능성도 함께 전달
- SPEC.md 10장 Reviewer 체크리스트 3건 완료 처리 및 발견 사항 반영

#### Removed (Planner — data/en/Phishing_Email.csv 삭제)
- 사용자가 예비용으로 추가한 18,650건짜리 영어 데이터셋(Safe/Phishing) 검사
- 구조는 정상(균형 61:39)이나 **"Safe" 클래스가 Enron 사내메일로 오염**(최빈단어 중 'enron' 678회,
  "equistar deal tickets" 등 Enron 업무용어) — 이미 3회(Enron/spam_or_not_spam/completeSpamAssassin)
  겪고 폐기한 것과 동일한 채널편향 함정
- 현재 영어 모델(completeSpamAssassin 기반, F1 0.957, OOD 10/10)에 섞으면 검증된 성능을 되레
  후퇴시킬 위험 → 사용 안 하기로 확정, 파일 삭제

#### Added (Planner — 자동 재학습: 피드백 임계치 + 안전장치 + 핫 리로드)
- 요청: 피드백 반영 → 재학습 → 성능 향상까지 **자동화** 가능한지 → "피드백 N건마다 자동" 방식으로 확정
- `src/train.py`, `src/train_en.py` : 핵심 로직을 `run_training()`(학습+평가, 저장 안 함)으로 분리,
  `main()`은 기존과 동일하게 학습+저장+DB기록(CLI 수동 실행 동작 100% 유지)
- `src/auto_retrain.py` 신규 :
  - `check_and_retrain_async()` — 언어별(ko/en) "마지막 시도 이후 새 피드백 수"가
    `AUTO_RETRAIN_THRESHOLD`(기본 5) 이상이면 백그라운드 스레드로 재학습(논블로킹)
  - **안전장치**: 새 F1이 기존 배포 모델보다 `AUTO_RETRAIN_MAX_F1_DROP`(기본 0.02) 넘게 나쁘면
    모델 파일을 덮어쓰지 않고 배포 보류(기존 모델 유지), `<version>-skipped`로 시도만 기록
    (재시도 폭주 방지: 다음 카운트 기준점이 이 시도 시점으로 갱신됨)
  - **핫 리로드**: 배포 성공 시 `predict_router.reload_ko()/reload_en()` 호출 → 실행 중인 앱이
    재시작 없이 다음 예측부터 새 모델 사용
- `src/predict_router.py` : `reload_ko()`, `reload_en()` 추가 (예측기 캐시 무효화)
- `src/database.py` : `save_report()` 저장 직후 `check_and_retrain_async()` 자동 호출(트리거 지점 1곳으로 통합
  → 홈 등록/Gmail "스팸 아님" 등 save_report를 부르는 모든 경로에서 자동 적용됨)
- `config.py`/`config.example.py` : `AUTO_RETRAIN_ENABLED/THRESHOLD/MAX_F1_DROP` 추가
- **실제 검증**: 실제로 쌓여있던 한국어 피드백 16건(임계치 초과)으로 트리거 → 재학습 →
  **F1 0.968→0.970 개선 확인 → 자동 배포** → `reload_ko()` 후 재조회 시 정상 재로드(핫 리로드 확인)
  → `save_report()` 트리거 연결도 실제 호출로 검증(에러 없음, 임계치 미달 시 조용히 종료)
- **정직한 한계**: 매번 처음부터 재학습(fine-tuning 아님)이라 전체 F1은 안정적이어도
  개별 문장 판정은 재학습마다 소폭 흔들릴 수 있음(진단 10문장 세트 9/10↔8/10 변동 확인,
  버그 아님·안전장치는 F1 집계 기준이라 이 변동은 못 막음 — SPEC 7-1장에 명시)
- SPEC.md : 기능 13(자동 재학습) 완료 추가, 7-1장에 동작 다이어그램·검증 결과·한계 신설

#### Changed (Designer — 홈 화면 본문 입력창 확장, 하단 여백 제거)
- 홈 화면 하단에 빈 여백이 남는다는 피드백 → `input_card`를 `fill="x"` → `fill="both", expand=True`로 변경해 남는 세로 공간을 흡수하도록 하고, 그 안의 `body_box`(본문 입력창)도 `fill="both", expand=True`로 바꿔 카드 안에서 실제로 늘어나는 요소가 되도록 함(제목/발신자 입력줄·첨부파일줄·버튼은 기존처럼 고정 높이 유지)
- 결과 카드/통계 카드는 기존과 동일하게 고정 높이로 아래 배치 — 겹침·잘림 없음
- 검증: `py_compile` + 헤드리스로 창 1280×800에서 본문 입력창 높이 90→234px 확장, input/result/stats 카드 y좌표·높이 겹침 없음 확인 후 실행 중이던 구버전 프로세스 종료 후 재실행

#### Changed (Designer — Gmail 목록 행에 발신자 표시, 2줄 레이아웃)
- 목록에 제목만 보여 발신자를 알 수 없다는 피드백 → 각 행을 상단(발신자)/하단(제목 미리보기) 2줄로 재구성
  (스크롤 영역이라 세로 공간 여유 있어 1줄 제약 없이 확장)
- 발신자는 `_title_preview(sender, limit=60)` 재사용해 60자 초과 시 "…" 처리, 발신자 없으면 "(발신자 없음)" 표시, 색상은 제목보다 옅은 `TEXT_MUTED`로 위계 구분
- 체크박스/색도트/발신자줄/제목줄 어디를 클릭해도 체크 토글되도록 바인딩 확장
- 검증: `py_compile` + 헤드리스로 행 10개 렌더, 각 행 text_col에 발신자 라벨·제목 라벨 2개가 정확히 들어가는지 확인 후 실행 중이던 구버전 프로세스 종료 후 재실행

#### Added (Planner — 영어용 피드백 루프)
- `src/train_en.py` : `load_user_reports_en()` 추가 — `user_reports`에서 **한글이 없는 행만** 조회
  (`train.py`의 한글 전용 필터와 정확히 상호 배타적 → 같은 테이블을 공유해도 언어별로 안 섞임)
- 한국어와 동일 원칙: train/test 분리 **이후** 학습셋에만 반영(누수 방지), `FEEDBACK_OVERSAMPLE=5`로 가중
- **검증(실제 시연)**: 애매하게 판정되던 영어 문장 2건("Notion...", "Roboflow...", 각 58.9%/69.9% "검토")을
  정상으로 등록 → 재학습 → **0.8%/3.5% "정상"으로 교정**. 기존 OOD 테스트 8건도 회귀 없이 유지 → **OOD 10/10**
- 등록한 피드백은 실제 개선 효과가 있어 삭제하지 않고 유지(스모크테스트용 더미 데이터와는 다름)
- SPEC.md : 기능 12(영어 피드백 루프) 완료로 갱신, 9장 미완목록·Planner 체크리스트 최신화

#### Added (Designer — 홈 페이지에 언어 라우터 적용)
- SPEC.md 신규 TODO 반영: 홈 판정을 한국어 고정 `SpamPredictor` → `predict_router.predict_email_tier_auto()`로 교체 (`app/app.py` `on_check()`)
- 반환값이 `(tier, prob, lang)`으로 하나 늘어남 — 결과 칩에 "감지 언어 KO/EN" 표시 추가(스팸 확률 옆에 병기)
- 신뢰 발신자 override, DB 저장(이진 `db_label`) 등 기존 로직은 그대로 유지, 판정 호출부만 교체
- 데모 시연(`run_demo`)은 한국어 데모 데이터셋 전용이라 기존 `SpamPredictor.predict()` 그대로 유지(범위 밖)
- 검증: `py_compile` 통과, 헤드리스로 영어 입력("Your package has shipped...") → EN 감지, 한국어 입력("회의 일정 안내...") → KO 감지 및 각 언어 전용 모델 확률 정상 반환 확인 후 실제 앱 재실행

#### Added (Planner — 영어 전용 모델 완성: 단어 단위 LSTM + 언어 라우터)
- 배경: 글자 단위는 영어에서 3회 실패(Enron/spam_or_not_spam/completeSpamAssassin, 합성 보강 포함).
  원인은 데이터가 아니라 "토큰화 단위" — 영어는 **단어 단위**가 필요함이 이전 조사로 입증됨
- `src/preprocessing_en.py` : 영어 단어 단위 토큰화(소문자화, `<url>`/`<num>` 치환, 아포스트로피 처리)
- `src/build_dataset_en.py` : 기존 `build_dataset.py`의 `load_english()`/`load_english_synth()` 재사용
  → `data/spam_en.csv` (ham 1640 / spam 1305, completeSpamAssassin 2000 + 합성 945)
- `src/train_en.py` : `model.py`의 `SpamLSTM`(범용) 재사용, MAX_LEN=300단어(중앙값 91·75%ile 202단어 커버)
  → **test Acc 0.963 / F1 0.957**
- `src/predict_en.py` : `EnglishSpamPredictor` — 한국어 `SpamPredictor`와 완전히 동일한 API(predict/predict_email/predict_tier/predict_email_tier)
- **검증(OOD, 이전에 실패했던 동일 문장)**: "lunch tomorrow / order shipped / quarterly report /
  happy birthday / appointment confirmed / 당첨·의약품·대출 스팸" → **8/10 정답**
  (이전 글자단위 시도들은 2~3/8 수준). 나머지 2건(홍보성 뉴스레터)은 3단계 판정에서 **"검토"로 합리 처리**
  → 2단계뿐 아니라 3단계 기준으로도 사실상 10/10 적절
- `src/predict_router.py` : `predict_email_tier_auto()` — 본문 한글 포함 여부로 언어 감지 후
  한국어/영어 예측기로 자동 라우팅(지연 로드 + 캐시)
- `src/gmail_pipeline.py` : Korean-only `SpamPredictor` → **`predict_router` 라우팅으로 교체**
  (Gmail은 이제 영어 메일도 전용 모델로 정확히 판정됨). `model_version`에 언어 태그(`v1` / `v1-en`) 반영
- `config.py`/`config.example.py` : `MODEL_PATH_EN`, `VOCAB_PATH_EN`, `MODEL_VERSION_EN`, `DATASET_PATH_EN` 추가
- 검증: 라우터 단위테스트(ko/en 자동감지·해당 모델 로드) 통과. `.gitignore`는 기존 와일드카드로 신규 산출물 자동 커버
- SPEC.md : 기능 10(영어 모델) 완료로 갱신, 모듈맵·API·데이터구조·성능표 반영, Designer 체크리스트 최신화(이미 완료된
  페이지네이션/필터/발신자신뢰 항목 [x] 정정), 신규 TODO(홈 페이지 라우터 적용/영어 피드백 루프) 추가

#### Changed (Designer — Gmail 필터 토글 가독성 개선 + 목록 미리보기/여백 정리)
- `CTkSegmentedButton`은 선택/비선택 텍스트 색을 따로 지정할 수 없음(`inspect.signature`로 확인) → 크기 확대(가변폭→`width=280, height=38`) + 굵은 고대비 흰색(`TEXT`) 폰트로 선택 여부와 무관하게 잘 보이도록 변경
- Gmail 목록 미리보기 글자수 제한 78 → 200자로 완화("…"는 실제 초과 시에만 표시)
- 필터 토글과 목록 사이 빈 공간이 넓다는 피드백 → filter_row 하단 패딩 6→1, 상태 라벨(빈 텍스트일 때도 자리 차지) 패딩 제거, 목록 상단 패딩 4→1로 축소
- 토글 좌우 여백이 좁다는 피드백 → filter_row 좌우 패딩 14→18로 확대
- 검증: `py_compile` + 헤드리스로 세그먼트버튼 `width/height/text_color` 값, 목록 10건 정상 렌더 확인, 실행 중이던 구버전 프로세스 2개 종료 후 재실행하여 반영 확인

#### Added (Designer — Gmail 목록 [스팸][정상][전체] 라벨 필터)
- `ctk.CTkSegmentedButton`으로 3단 토글 추가, 기본값 "스팸" (Planner 요청: 정상 오탐 대비 스팸이 기본으로 보이게)
- `database.fetch_gmail_pending(limit, offset, label=...)` / `count_gmail_pending(label=...)`(Planner 신규 API) 사용 — "스팸"→'spam', "정상"→'ham', "전체"→None
- 필터 전환 시 1페이지로 리셋
- 검증: 헤드리스로 스팸 53건/정상 36건/전체 89건(53+36 일치) 필터별 카운트 확인

#### Changed (Designer — 색 이모지를 아이콘/색 도트로 전면 교체)
- 사용자가 제공한 단색 실루엣 PNG 세트(`data/img/`: 홈/기록/Gmail/즐겨찾기/닫기/최소화/화살표, 512x512 투명배경)를 `load_icon(filename, color, size)` 헬퍼로 재색상 처리해 사용
  (알파 채널을 마스크로 써서 원하는 색으로 tint → `ctk.CTkImage`) — 사이드바 활성/비활성 두 색상 버전을 각각 만들어 페이지 전환 시 `image=` 교체
- 사이드바 4개 아이콘, 타이틀바 앱 아이콘/닫기/최소화 버튼을 색 이모지(🏠📋📥⭐📧✕─) → 아이콘 이미지로 교체
- 판정 결과 3단계(스팸/검토/정상) 표시를 🔴🟡🟢 → 색 도트(●, 기존 tier 색상 그대로)로 교체. Gmail 목록 행도 체크박스+색도트+제목 레이아웃으로 재구성(도트/제목 클릭도 체크박스 토글되도록 바인딩)
- 판정하기/스팸등록/정상등록/삭제/스팸처리/스팸아님/발신자신뢰 등 버튼은 이미 한글 텍스트+색상 구분이 있어 이모지만 제거(텍스트+배경색 유지)
- 트레이 메뉴, 신뢰 발신자 안내문 등 나머지 이모지도 정리. 종료 버튼(⏻)은 색이 없는 단색 기호라 다크테마에 문제없어 유지
- 참고: pystray는 Windows 트레이 우클릭 메뉴 항목에 개별 아이콘을 지원하지 않아 arrow(확장) 아이콘은 이번엔 미사용으로 보류
- 검증: 헤드리스로 아이콘 로드/사이드바 4페이지 전환/Gmail 목록 렌더링 확인, `py_compile` 통과 후 실제 앱 실행 확인

#### Added (Designer — Gmail 목록 페이지네이션 UI)
- Gmail 목록에 "◀ 이전 / n·총페이지(총 건수) / 다음 ▶" 컨트롤 추가 — `database.fetch_gmail_pending(limit, offset)` + `count_gmail_pending()`(Planner 신규 API), `config.GMAIL_PAGE_SIZE`(10) 사용
- 페이지 범위를 벗어나면(항목 조치/새 가져오기 등으로 총 개수 변동) 자동으로 유효 범위로 clamp, 첫/마지막 페이지에서 이전/다음 버튼 비활성화
- 새로 가져오기 완료 시 1페이지로 리셋해 최신 메일부터 보이도록 처리
- 검증: 헤드리스로 실제 미조치 17건 → 10+7건 2페이지 분할, 다음/이전 이동 시 목록·버튼 상태·페이지 라벨이 올바르게 갱신되는지 확인

#### Changed (Designer — Gmail 페이지 레이아웃 축소 + 발신자 신뢰 버튼 추가)
- 상단의 큰 "📥 Gmail 가져오기" 카드(설명 2줄 + 큰 버튼)를 없애고, 목록 카드 헤더 줄에 작은 "↻ 가져오기" 버튼으로 통합 — 메일 목록이 페이지의 주된 영역이 되도록 공간 재배분(목록 높이 220→400)
- Gmail 목록 액션을 3버튼 → **4버튼**으로 확장: 기존 [삭제][스팸처리][스팸아님]에 **"발신자 신뢰"** 추가
  → `database.trust_senders_by_gmail_ids(선택된_gmail_ids, use_domain=False)` 호출(Planner가 추가한 신규 API), 확인창 후 실행
- 검증: 헤드리스로 실제 gmail_id 1건 선택 → 신뢰 등록 → `is_trusted` True 확인 → 테스트 데이터 정리(실사용 데이터 영향 없음)

#### Added (Planner — Gmail 목록 라벨 필터: 기본 스팸만)
- 문제: 아이콘/색으로 스팸·정상 구분이 잘 안 보인다는 피드백 → 목록 자체를 라벨로 필터링해 구분 필요성을 줄임
- `database.fetch_gmail_pending(limit, offset, label='spam')`, `count_gmail_pending(label='spam')`
  — label: 'spam'(기본) | 'ham' | None(전체)
- 검증: spam 60건 / ham 36건 / 전체 96건, 각 필터가 해당 라벨만 정확히 반환 확인
- 용어 정리: **오탐**(정상→스팸 오판, 기본 스팸필터로 확인) / **미탐**(스팸→정상 놓침, 'ham' 필터로 확인)
- Designer 할일(SPEC): [스팸][정상][전체] 토글 버튼, 기본값 스팸, 전환 시 페이지 리셋

#### Added (Planner — Gmail 더 많이 가져오기 + 목록 페이지네이션)
- `config.py` : `GMAIL_FETCH_COUNT` 20 → 100, `GMAIL_PAGE_SIZE=10` 추가
- `gmail_service.fetch_recent` : n>500 시 pageToken 넘겨가며 수집(대량 대응)
- `database.py` : `fetch_gmail_pending(limit, offset)`(페이지네이션), `count_gmail_pending()`(총 개수)
- 검증: 미조치 17건 → 페이지크기 10 → 2페이지(10+7) 정상
- Designer 할일(SPEC): Gmail 목록에 이전/다음 페이지 + "n/총 페이지" 표시 (offset·count API 사용)

#### Added (Planner — 목록에서 발신자 클릭 신뢰 등록)
- `database.py` : `add_trusted_from_sender(sender, use_domain)`, `trust_senders_by_gmail_ids(gmail_ids, use_domain)`
  — 직접 타이핑 대신, 선택 메일의 **발신자를 추출해 신뢰 목록에 등록** (이메일/도메인 선택)
- 검증: 'Notion <team@mail.notion.so>' → 이메일/도메인 추출·등록·is_trusted 확인
- Designer 할일(SPEC): Gmail 목록에 "이 발신자 신뢰" 액션 → `trust_senders_by_gmail_ids`

#### Added (Planner — 처리된 Gmail 메일 목록에서 숨김)
- 진단: 스팸처리 버튼은 **정상 작동**(실제 스팸함 이동 확인). 처리 후에도 목록에 남아 "안 되는 것처럼" 보였음
- `messages.actioned` 컬럼 + 마이그레이션. `fetch_gmail_pending()`(미처리만), `mark_gmail_actioned()`
- `app.py`(기능 배선, Planner): Gmail 목록을 `fetch_gmail_pending`로, 조치 성공 시 `mark_gmail_actioned` 호출
  → 삭제/스팸/스팸아님 처리한 메일은 목록에서 사라짐 (기록·통계는 보존)

#### Fixed / Changed (Designer — 트레이 앱 마무리 다듬기)
- **버그 수정**: 타이틀바/사이드바에 `grid_propagate(False)`를 잘못 호출하고 있었음 — 두 프레임의 자식은 모두 `pack()`으로 배치되므로 올바른 호출은 `pack_propagate(False)`. 이 때문에 사이드바 안의 투명 스페이서(기본 200px)가 실제 폭을 끌어올려, 사이드바 폭을 줄여도 화면엔 반영되지 않던 문제 해결 (헤드리스로 `winfo_reqwidth()` 250→45(스케일 반영 36px) 확인)
- 사이드바 폭을 아이콘 버튼과 동일하게(36px) 축소, 신뢰 발신자 아이콘 추가
- 첫 실행 시 트레이에 숨지 않고 바로 창이 뜨도록 변경 (`root.withdraw()` 제거) — X/─ 버튼으로 트레이로 숨기는 동작은 유지
- `overrideredirect(True)` 창은 기본적으로 작업표시줄에서 숨겨지므로, Windows 확장 스타일(`WS_EX_APPWINDOW`)을 직접 설정해 작업표시줄 아이콘 강제 표시 + 트레이 아이콘과 동일한 창 아이콘(`iconphoto`) 적용
- "기록" 페이지 내용 미리보기: 전체 내용 노출(가로 스크롤) → `\r` 잔여문자로 인한 표시 잘림 버그 수정 → 최종적으로 "제목" 열 50~80자 미리보기 + 세로 스크롤로 정착(가로 스크롤 제거, 가독성 우선)
- Gmail 일괄처리 3버튼: 버튼 아래 별도 설명 문구 줄 → 버튼 자체에 2줄 텍스트로 통합(예: "삭제\n(휴지통, 복구가능)")해 더 직관적으로 정리, "학습" 표현 제거
- 창 크기 640×640 → **1024×640**으로 확대(모니터 해상도 2048×1280 = 16:10 비율에 정확히 맞춤)
- 창 폭 확대 비율(1.6배)에 맞춰 글자수 제한/줄바꿈 폭 조정: 제목 미리보기 50→80자, 데모 오답 미리보기 45→70자, 결과 카드 wraplength 360→580, Gmail 상태 wraplength 560→900, 기록 "제목" 컬럼 폭 260→420
- 검증: 매 변경마다 `py_compile` + 헤드리스 스크립트(위젯 재구성 후 실제 렌더 크기/텍스트 길이 확인)로 우선 검증 후 실제 앱 실행 확인

#### Added (Planner — "스팸 아님" 처리 + 조치 의미 명확화)
- `gmail_service.py` : `apply_action`에 `'not_spam'` 추가 (받은편지함 복귀 + SPAM 라벨 제거)
- `gmail_pipeline.py` : `mark_not_spam(gmail_ids)` — 정상(ham) 피드백 등록(모델 학습) + Gmail 스팸함 복귀 종합
- `database.py` : `get_content_by_gmail_id()` (피드백 등록용 본문 조회)
- SPEC: Gmail 3버튼(삭제=휴지통 / 스팸처리=스팸함 / 스팸아님=정상+학습) 의미표 + Designer 문구/툴팁 지시

#### Added (Designer — 신뢰 발신자 관리 페이지 + 홈 판정 override)
- 사이드바에 신뢰 발신자 페이지 신규 추가 — `database.add/remove/fetch_trusted_senders()` 호출
  - 추가 카드(패턴+메모 입력) / 목록 카드(행별 삭제 버튼, `CTkScrollableFrame`)
- 홈 페이지 `on_check()`에 `database.is_trusted(sender)` 체크 추가 → 신뢰 발신자면 모델 결과와 무관하게 정상(prob 0.0)으로 override 표시
- DB 연결 실패 시에도 판정이 죽지 않도록 `is_trusted` 호출을 try/except로 감쌈(기본값 신뢰 안 함)
- 검증: 헤드리스로 신뢰 발신자 추가→목록 반영→삭제(테스트 데이터는 정리, 실사용 데이터 영향 없음), `is_trusted` 서브도메인 매칭 확인

#### Changed (Designer — Gmail 일괄 처리 2버튼 → 3버튼 + 설명 문구)
- Gmail 페이지 체크박스 목록 액션을 [선택 삭제][선택 스팸처리] 2버튼 → **3버튼**으로 확장, "스팸 아님" 추가(`gmail_pipeline.mark_not_spam` 호출)
- 각 버튼 아래에 "삭제=휴지통(30일 복구) / 스팸처리=스팸함(필터 학습) / 스팸아님=정상+학습(스팸함 복귀)" 설명 문구 추가(SPEC "Gmail 목록 버튼 문구" 표 반영)
- 확인 다이얼로그 문구도 조치별로 구체화(복구가능/필터학습/모델학습 등 결과를 명시)
- SPEC.md 갱신: Designer 체크리스트 전 항목 완료 체크, 기능 상태표(7/8/9b) 완료로 갱신

### 2026-07-09

#### Added (Planner — 신뢰 발신자 allowlist)
- `db_schema.sql` : `trusted_senders` 테이블 (pattern=이메일/도메인)
- `database.py` : `add/remove/fetch_trusted_senders`, `is_trusted(sender)` (이메일/도메인 매칭, **서브도메인 포함**), `extract_email()`
- `gmail_pipeline.py` : 신뢰 발신자면 모델 무관하게 **정상(ham)으로 override**
- 규칙 계층(모델과 별개): 신뢰 발신자 → 무조건 정상. 검증: notion.so 등록 시 team@mail.notion.so도 신뢰
- Designer 할일(SPEC): 신뢰 발신자 관리 UI + 홈 판정 override 표시

#### Added (Planner — Gmail 사용자 조치: 선택 삭제/스팸처리)
- `gmail_service.py` : `apply_action(gmail_ids, action)` — 'trash'(휴지통,복구가능) / 'spam'(SPAM 라벨+INBOX 제거)
- 스코프 `gmail.readonly` → **`gmail.modify`**. 영구삭제(mail.google.com) 미사용. token.json 삭제 → 재인증 1회 필요
- 안전: 반드시 사용자 선택+확인 후 실행, 휴지통은 30일 복구 가능
- Designer 할일(SPEC): Gmail 목록 체크박스 + 전체선택 + [선택 삭제][선택 스팸처리] → `apply_action`

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
- `predict.py` : `to_tier()`, `predict_tier()`, `predict_email_tier()` — 스팸/검토/정상
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
- 판정 결과를 **3단계 3색**(스팸 / 검토 필요 / 정상 + 확률)으로 표시 (SPEC.md 7장 색 매핑 기준)
- 등록 버튼은 4필드를 합친 내용으로 `database.save_report()` 호출 (기존과 동일 흐름)
- 알아둘 점: `messages.predicted_label`이 `ENUM('ham','spam')`이라 `'review'`를 그대로 저장할 수 없음
  → DB 저장 시에는 `SPAM_THRESHOLD`(0.5) 기준 이진값으로 매핑해 저장하고, 화면 표시만 3단계로 분리
  (스키마에 `'review'`를 추가하려면 Planner/DB 쪽 변경 필요 — 이번 변경 범위 밖)
- 실행 검증: `python main.py app` (conda env `spam_detector`) 컴파일·정상 실행·정상 종료 확인

#### Added (Designer — Gmail 가져오기 UI, SPEC.md 9b 반영)
- 트레이 메뉴 "Gmail 가져오기" 추가 → `gmail_pipeline.run()`을 별도 스레드에서 실행(SPEC 권장대로 브라우저 인증 대기가 UI를 막지 않게), 완료/실패 결과는 팝업으로 표시
- 메인창에 ☰ 메뉴 버튼 추가(최근 기록/Gmail 가져오기/데모 시연/트레이로 숨기기/종료) — 트레이 우클릭 없이도 창 안에서 같은 동작 접근 가능

#### Changed (Designer — PC Manager 스타일 다크 카드 UI로 전면 재설계)
- 사용자가 제시한 레퍼런스 이미지(Microsoft PC Manager) 기준으로 `app/app.py` UI 전면 재작성
  - OS 제목표시줄 제거(`overrideredirect`) 후 커스텀 다크 타이틀바(─/✕) + 직접 드래그 구현
  - 좌측 아이콘 사이드바(홈 / 기록 / Gmail / ⏻종료)로 3개 페이지 전환(`tkraise`) — 기존 ☰ 메뉴와 팝업창(이력/Gmail)을 제거하고 인앱 페이지로 흡수
  - 다크 카드 팔레트 적용(`BG/SIDEBAR_BG/CARD_BG/CARD_BG_ALT/ACCENT` 등), 홈 페이지를 입력/결과/통계 3개 카드로 구성
  - Gmail 가져오기는 팝업 대신 페이지 내 상태 라벨로 인라인 표시
- 백엔드 API(`predict_email_tier`, `database.*`, `gmail_pipeline.run`) 호출부는 변경 없음

#### Fixed (Designer — 다크 UI 후속 버그 수정 및 조정)
- **사이드바가 줄어들지 않던 버그**: `pack()`으로 자식을 넣은 프레임(타이틀바/사이드바)에 `grid_propagate(False)`를 잘못 적용 — 올바른 호출인 `pack_propagate(False)`로 수정. 내부 투명 스페이서(기본 200px)가 프레임 크기를 부풀리던 원인 제거. 헤드리스 테스트로 실제 렌더 폭(36px→45px, 125% DPI 반영) 검증 완료
- **작업표시줄에 앱이 안 뜨던 문제**: `overrideredirect(True)` 창은 기본적으로 작업표시줄에서 숨겨짐 → `ctypes`로 Windows 확장 스타일(`WS_EX_APPWINDOW`) 강제 적용 + 트레이 아이콘과 동일한 이미지로 창 아이콘(`iconphoto`) 설정
- **기록 페이지 내용이 잘려 보이던 문제**: 원인은 저장 데이터가 아니라(DB 직접 조회로 본문 전체 정상 저장 확인, Gmail 건은 최대 5000자) 표시 단계에서 `\r`(캐리지리턴)을 치환하지 않아 발생 — 이후 요구사항 변경으로 표시 자체를 "제목 미리보기"(50자, `제목: ` 접두어 제거) 방식으로 단순화하며 근본 해결
- 첫 실행 시 트레이에 숨어있던 것 → 바로 창이 뜨도록 변경(`root.withdraw()` 제거), ✕/─ 버튼은 여전히 트레이로 숨기는 용도로 유지
- 창 크기 480x460 → 640x640, 사이드바 폭 64→36(아이콘 크기와 동일)로 조정
- 실행 검증: `python main.py app` 반복 실행 + 헤드리스 스크립트로 위젯 크기·트리 데이터 직접 확인

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
- `app/app.py` 완성: 판정&저장 + 최근목록/통계 + 스팸/정상 등록 + 데모 시연
- `database.py` : `save_report`, `fetch_reports`, `count_reports` 추가 (user_reports 연동)
- 스모크 테스트 통과 (import/통계/데모/등록 정상, 데모 120건 100%)

#### Fixed (링크 편향)
- 문제: 합성 스팸은 거의 링크 有 / 합성 정상은 링크 無 → 모델이 `<url>`을 과대평가
  (정상 메일에 링크 있으면 스팸 오판)
- 해결: `make_seed_data.py` — 템플릿에서 {링크} 제거, 라벨과 무관하게 ~50% 랜덤 부착
- 검증(A/B): 같은 문장에 링크 추가 시 스팸확률 변화 +0.0~0.5p (거의 무영향) → 해결
- 재학습 성능: 전체 0.937 / 한국어 0.968 / 영어 0.906
- 잔여(별개): "배송" 등 특정 단어가 피싱 스팸과 겹쳐 오판 — 링크와 무관