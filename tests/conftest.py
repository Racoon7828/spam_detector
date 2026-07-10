"""pytest 공통 설정: 프로젝트 루트를 sys.path 에 추가해 `from src...` / `from config...` import 가능하게."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
