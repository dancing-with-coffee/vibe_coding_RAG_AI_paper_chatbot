"""
데이터 모델 및 스키마 정의
Pydantic 스키마와 SQLAlchemy 모델을 정의합니다.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import json


# ==================== Pydantic 스키마 ====================

class PDFDocumentBase(BaseModel):
    """PDF 문서 기본 스키마"""
    original_filename: str = Field(..., description="원본 파일명")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    page_count: int = Field(..., description="페이지 수")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="메타데이터")


class PDFDocumentCreate(PDFDocumentBase):
    """PDF 문서 생성 스키마"""
    pass


class PDFDocumentUpdate(BaseModel):
    """PDF 문서 업데이트 스키마"""
    vectorization_status: Optional[str] = Field(None, description="벡터화 상태")
    metadata: Optional[Dict[str, Any]] = Field(None, description="메타데이터")


class PDFDocumentResponse(PDFDocumentBase):
    """PDF 문서 응답 스키마"""
    id: UUID
    filename: str
    upload_date: datetime
    vectorization_status: str
    vectorization_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageBase(BaseModel):
    """채팅 메시지 기본 스키마"""
    content: str = Field(..., description="메시지 내용")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="메타데이터")


class ChatMessageCreate(ChatMessageBase):
    """채팅 메시지 생성 스키마"""
    message_type: str = Field(..., description="메시지 타입 (user/assistant)")
    session_id: str = Field(..., description="세션 ID")


class ChatMessageResponse(ChatMessageBase):
    """채팅 메시지 응답 스키마"""
    id: UUID
    session_id: UUID
    message_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionBase(BaseModel):
    """채팅 세션 기본 스키마"""
    session_id: str = Field(..., description="세션 ID")


class ChatSessionCreate(ChatSessionBase):
    """채팅 세션 생성 스키마"""
    pass


class ChatSessionResponse(ChatSessionBase):
    """채팅 세션 응답 스키마"""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """채팅 요청 스키마"""
    message: str = Field(..., description="사용자 질문")
    session_id: str = Field(..., description="세션 ID")
    pdf_ids: Optional[List[UUID]] = Field(default=None, description="PDF ID 목록")


class ChatResponse(BaseModel):
    """채팅 응답 스키마"""
    answer: str = Field(..., description="챗봇 답변")
    sources: List[Dict[str, Any]] = Field(..., description="출처 정보")
    session_id: str = Field(..., description="세션 ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SourceInfo(BaseModel):
    """출처 정보 스키마"""
    content: str = Field(..., description="인용된 텍스트")
    page_number: int = Field(..., description="페이지 번호")
    pdf_filename: str = Field(..., description="PDF 파일명")
    similarity_score: float = Field(..., description="유사도 점수")


class UploadResponse(BaseModel):
    """업로드 응답 스키마"""
    message: str = Field(..., description="응답 메시지")
    pdf_id: UUID = Field(..., description="PDF ID")
    filename: str = Field(..., description="저장된 파일명")
    status: str = Field(..., description="업로드 상태")


class VectorizationStatus(BaseModel):
    """벡터화 상태 스키마"""
    pdf_id: UUID
    status: str = Field(..., description="벡터화 상태")
    progress: Optional[float] = Field(None, description="진행률 (0-100)")
    message: Optional[str] = Field(None, description="상태 메시지")


class HealthCheck(BaseModel):
    """헬스 체크 응답 스키마"""
    status: str = Field(..., description="서비스 상태")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(..., description="각 서비스 상태")


# ==================== SQLAlchemy 모델 ====================

from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base
import uuid


class PDFDocument(Base):
    """PDF 문서 모델"""
    __tablename__ = "pdf_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    page_count = Column(Integer, nullable=False)
    upload_date = Column(DateTime(timezone=True), default=datetime.utcnow)
    vectorization_status = Column(String(50), default="pending")
    vectorization_date = Column(DateTime(timezone=True))
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    session_pdfs = relationship("SessionPDF", back_populates="pdf_document")


class ChatSession(Base):
    """채팅 세션 모델"""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    session_pdfs = relationship("SessionPDF", back_populates="session")


class ChatMessage(Base):
    """채팅 메시지 모델"""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    message_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # 관계
    session = relationship("ChatSession", back_populates="messages")


class SessionPDF(Base):
    """세션-PDF 연결 모델"""
    __tablename__ = "session_pdfs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    pdf_id = Column(UUID(as_uuid=True), ForeignKey("pdf_documents.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # 관계
    session = relationship("ChatSession", back_populates="session_pdfs")
    pdf_document = relationship("PDFDocument", back_populates="session_pdfs")


# ==================== 유틸리티 함수 ====================

def validate_pdf_file(filename: str, file_size: int, page_count: int) -> bool:
    """PDF 파일 유효성 검사"""
    if not filename.lower().endswith('.pdf'):
        return False
    
    if file_size > 20 * 1024 * 1024:  # 20MB
        return False
    
    if page_count > 300:
        return False
    
    return True


def create_session_id() -> str:
    """고유한 세션 ID 생성"""
    import time
    import random
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(1000, 9999)
    return f"session_{timestamp}_{random_suffix}"
