"""Vercel 서버리스 진입점 — FastAPI ASGI 앱을 노출."""
import os
import sys

# 프로젝트 루트를 import 경로에 추가 (web, barcode_papers 패키지)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.app import app  # noqa: E402

# Vercel @vercel/python 런타임이 'app'(ASGI)을 자동 인식
