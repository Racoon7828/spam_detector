# Changelog

## [Unreleased]

### 2026-07-10

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

#### TODO (선택)
- [ ] 정상 배송/알림 문장 추가로 단어 편향 완화
- [ ] 재학습에 user_reports 반영
- [ ] 나이브 베이즈 베이스라인 비교
- [ ] 모델 학습 및 평가
- [ ] 데스크탑 앱 동작 확인
