"""
애플리케이션 설정 관리
환경 변수와 기본 설정값을 관리합니다.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # 기본 애플리케이션 설정
    APP_NAME: str = "RAG Paper Chatbot"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API 설정
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # CORS 설정
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ]
    
    # 데이터베이스 설정
    DATABASE_URL: str = "postgresql://rag_user:rag_password@localhost:5432/rag_paper_db"
    
    # ChromaDB 설정
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_URL: str = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    
    # OpenAI API 설정
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-ada-002"
    
    # 파일 업로드 설정
    MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20MB
    MAX_PAGES: int = 300
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    
    # RAG 설정
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.7
    
    # 보안 설정
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 성능 설정
    VECTORIZATION_TIMEOUT: int = 60  # 1분
    RESPONSE_TIMEOUT: int = 5  # 5초
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # 환경별 설정 조정
        if self.ENVIRONMENT == "production":
            self.DEBUG = False
            self.CORS_ORIGINS = ["https://yourdomain.com"]  # 프로덕션 도메인으로 변경
        
        # ChromaDB URL 업데이트
        self.CHROMA_URL = f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"
        
        # 업로드 디렉토리 생성
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)


# 전역 설정 인스턴스
settings = Settings()
