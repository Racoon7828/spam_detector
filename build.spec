# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 빌드 스펙. onedir(디렉터리) 모드로 빌드한다(단일 exe onefile 아님).
이유: onefile은 실행할 때마다 임시 폴더(MEIPASS)에 압축을 풀고 종료 시 지워버려서,
이 앱이 실행 중 계속 써야 하는 파일들(spam_detector.log, models/*.pt 재학습 결과,
models/backups/, config/token.json Gmail 인증 캐시)이 실행할 때마다 사라진다.
onedir는 exe 옆의 dist/spam_detector/ 폴더가 그대로 남으므로 이 문제가 없다.

빌드:
    pyinstaller build.spec
결과물: dist/spam_detector/spam_detector.exe (+ 같은 폴더에 위 파일들이 남음, 삭제 금지)
"""
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden_imports = (
    collect_submodules("pystray")
    + collect_submodules("googleapiclient")
    + [
        "PIL._tkinter_finder",
        "pymysql",
        "google.auth.transport.requests",
        "google_auth_oauthlib.flow",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("data/img", "data/img"),                 # 트레이/사이드바 아이콘 (읽기 전용 리소스)
        ("data/synthetic/demo_samples.csv", "data/synthetic"),   # 데모 시연용 샘플
        ("models/spam_lstm.pt", "models"),        # 최초 배포 시 동봉할 학습된 모델(이후 자동재학습이 덮어씀)
        ("models/vocab.json", "models"),
        ("models/spam_lstm_en.pt", "models"),
        ("models/vocab_en.json", "models"),
        ("config/db_schema.sql", "config"),       # init_db.py 가 참조하는 스키마 파일
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "jupyter", "notebook", "pytest"],  # 앱 실행에는 불필요(학습/EDA 전용)
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="spam_detector",
    console=False,   # GUI 앱이므로 콘솔창 없이 실행 (문제 생기면 True 로 바꿔 로그 확인)
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="spam_detector",
)
