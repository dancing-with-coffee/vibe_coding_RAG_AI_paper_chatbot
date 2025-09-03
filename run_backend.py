#!/usr/bin/env python3
"""
백엔드 서버 실행 스크립트
"""
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from backend.main import app
    
    print("🚀 AI Research Papers RAG Chatbot 백엔드 서버 시작...")
    print("📖 PDF 파일들이 처음 실행시 자동으로 처리됩니다.")
    print("⚡ 서버 주소: http://localhost:8000")
    print("📚 API 문서: http://localhost:8000/docs")
    
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
