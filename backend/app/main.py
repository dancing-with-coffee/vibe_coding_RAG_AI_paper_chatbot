"""
RAG Paper Chatbot - FastAPI Main Application
논문 PDF를 업로드하고 RAG 기반 질문-답변을 제공하는 API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from contextlib import asynccontextmanager

from app.api.endpoints import pdf, chat, health
from app.core.config import settings
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 데이터베이스 초기화
    await init_db()
    print("🚀 RAG Paper Chatbot started successfully!")
    yield
    # 종료 시 정리 작업
    print("👋 RAG Paper Chatbot shutting down...")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="논문 PDF를 업로드하고 RAG 기반 질문-답변을 제공하는 API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (업로드된 PDF 파일)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# API 라우터 등록
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(pdf.router, prefix="/api/v1/pdf", tags=["pdf"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Welcome to RAG Paper Chatbot API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/info")
async def info():
    """애플리케이션 정보"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
