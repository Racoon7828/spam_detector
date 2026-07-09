# 📧 Spam Detector

딥러닝(LSTM) 기반 이메일/문자 스팸 분류기. 분류 결과를 **MySQL**에 저장하고,
가벼운 **데스크탑 앱**으로 켜서 관리한다.

## 기술 스택
- **언어**: Python 3.13
- **딥러닝**: PyTorch (LSTM 텍스트 분류)
- **DB**: MySQL
- **GUI**: CustomTkinter + pystray (시스템 트레이 상주형 메모창 스타일)

## 프로젝트 구조
```
spam_detector/
├── config/
│   ├── config.example.py   # 설정 템플릿 (복사해서 config.py 로 사용)
│   └── db_schema.sql       # MySQL 테이블 스키마
├── src/
│   ├── database.py         # MySQL 연결/저장/조회
│   ├── preprocessing.py    # 텍스트 전처리 + 어휘사전
│   ├── model.py            # LSTM 모델 정의
│   ├── train.py            # 모델 학습 스크립트
│   └── predict.py          # 저장된 모델로 예측
├── app/
│   └── app.py              # 데스크탑 관리 앱
├── data/                   # 학습 데이터셋 (git 제외)
├── models/                 # 학습된 모델 저장 (git 제외)
└── main.py                 # 진입점
```

## 시작하기

### 1. 가상환경 & 라이브러리
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 설정 파일 준비
```powershell
copy config\config.example.py config\config.py
# config.py 를 열어 MySQL 접속 정보 입력
```

### 3. DB 스키마 생성
```powershell
mysql -u root -p < config\db_schema.sql
```

### 4. 실행 순서
```powershell
python src\train.py      # 1) 모델 학습
python app\app.py        # 2) 관리 앱 실행
```

## 진행 상태
- [x] 프로젝트 구조 생성
- [ ] 데이터셋 준비 (SMS Spam Collection)
- [ ] 전처리 파이프라인
- [ ] LSTM 모델 학습
- [ ] MySQL 연동
- [ ] 데스크탑 앱
- [ ] (선택) Gmail API 연동
