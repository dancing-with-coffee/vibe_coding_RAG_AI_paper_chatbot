"""
채팅 API 엔드포인트
RAG 기반 질문-답변을 처리하고 대화 히스토리를 관리합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid

from app.db.database import get_db
from app.models.schemas import (
    ChatRequest, ChatResponse, ChatMessageCreate, ChatMessageResponse,
    ChatSessionCreate, ChatSessionResponse, SourceInfo
)
from app.models.schemas import ChatSession, ChatMessage, SessionPDF, PDFDocument
from app.core.config import settings
from app.core.rag_engine import RAGEngine
from app.core.vectorizer import Vectorizer

router = APIRouter()
logger = logging.getLogger(__name__)

# RAG 엔진 및 벡터라이저 인스턴스
rag_engine = RAGEngine()
vectorizer = Vectorizer()


@router.post("/session", response_model=ChatSessionResponse)
async def create_session(
    session_data: ChatSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """새로운 채팅 세션 생성"""
    try:
        # 세션 ID 중복 확인
        existing_session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_data.session_id)
        )
        
        if existing_session.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="이미 존재하는 세션 ID입니다")
        
        # 새 세션 생성
        new_session = ChatSession(session_id=session_data.session_id)
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        
        logger.info(f"새 채팅 세션 생성: {session_data.session_id}")
        
        return ChatSessionResponse.from_orm(new_session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")


@router.get("/session/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """특정 채팅 세션 조회"""
    try:
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return ChatSessionResponse.from_orm(session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"세션 조회 실패: {str(e)}")


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """질문에 대한 답변 생성 (RAG 기반)"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == chat_request.session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 사용자 메시지 저장
        user_message = ChatMessage(
            session_id=session.id,
            message_type="user",
            content=chat_request.message,
            metadata={"timestamp": datetime.utcnow().isoformat()}
        )
        db.add(user_message)
        await db.commit()
        
        # RAG 기반 답변 생성
        answer, sources = await rag_engine.generate_answer(
            chat_request.message,
            chat_request.pdf_ids or []
        )
        
        # 어시스턴트 메시지 저장
        assistant_message = ChatMessage(
            session_id=session.id,
            message_type="assistant",
            content=answer,
            metadata={
                "sources": [source.dict() for source in sources],
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(assistant_message)
        await db.commit()
        
        logger.info(f"질문 답변 생성 완료: {chat_request.session_id}")
        
        return ChatResponse(
            answer=answer,
            sources=[source.dict() for source in sources],
            session_id=chat_request.session_id,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"질문 답변 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"답변 생성 실패: {str(e)}")


@router.get("/session/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    session_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """세션의 메시지 히스토리 조회"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 메시지 조회
        messages = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        
        message_list = messages.scalars().all()
        return [ChatMessageResponse.from_orm(msg) for msg in message_list]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"메시지 히스토리 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


@router.post("/session/{session_id}/pdfs")
async def add_pdfs_to_session(
    session_id: str,
    pdf_ids: List[uuid.UUID],
    db: AsyncSession = Depends(get_db)
):
    """세션에 PDF 추가 (다중 PDF 지원)"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # PDF 존재 확인
        for pdf_id in pdf_ids:
            pdf = await db.execute(
                select(PDFDocument).where(PDFDocument.id == pdf_id)
            )
            pdf = pdf.scalar_one_or_none()
            
            if not pdf:
                raise HTTPException(status_code=404, detail=f"PDF를 찾을 수 없습니다: {pdf_id}")
            
            if pdf.vectorization_status != "completed":
                raise HTTPException(
                    status_code=400, 
                    detail=f"벡터화가 완료되지 않은 PDF입니다: {pdf.original_filename}"
                )
        
        # 세션에 PDF 연결
        added_pdfs = []
        for pdf_id in pdf_ids:
            # 중복 확인
            existing = await db.execute(
                select(SessionPDF).where(
                    SessionPDF.session_id == session.id,
                    SessionPDF.pdf_id == pdf_id
                )
            )
            
            if not existing.scalar_one_or_none():
                session_pdf = SessionPDF(
                    session_id=session.id,
                    pdf_id=pdf_id
                )
                db.add(session_pdf)
                added_pdfs.append(pdf_id)
        
        await db.commit()
        
        logger.info(f"세션에 PDF 추가: {session_id} -> {len(added_pdfs)}개")
        
        return {
            "message": f"{len(added_pdfs)}개의 PDF가 세션에 추가되었습니다",
            "added_pdfs": added_pdfs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 추가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 추가 실패: {str(e)}")


@router.get("/session/{session_id}/pdfs", response_model=List[Dict[str, Any]])
async def get_session_pdfs(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """세션에 연결된 PDF 목록 조회"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 연결된 PDF 조회
        session_pdfs = await db.execute(
            select(SessionPDF, PDFDocument)
            .join(PDFDocument, SessionPDF.pdf_id == PDFDocument.id)
            .where(SessionPDF.session_id == session.id)
        )
        
        pdf_list = []
        for session_pdf, pdf_doc in session_pdfs:
            pdf_list.append({
                "id": str(pdf_doc.id),
                "filename": pdf_doc.original_filename,
                "page_count": pdf_doc.page_count,
                "upload_date": pdf_doc.upload_date.isoformat(),
                "added_to_session": session_pdf.created_at.isoformat()
            })
        
        return pdf_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 PDF 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


@router.delete("/session/{session_id}/pdfs/{pdf_id}")
async def remove_pdf_from_session(
    session_id: str,
    pdf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """세션에서 PDF 제거"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 연결 제거
        session_pdf = await db.execute(
            select(SessionPDF).where(
                SessionPDF.session_id == session.id,
                SessionPDF.pdf_id == pdf_id
            )
        )
        session_pdf = session_pdf.scalar_one_or_none()
        
        if not session_pdf:
            raise HTTPException(status_code=404, detail="세션에 연결된 PDF를 찾을 수 없습니다")
        
        await db.delete(session_pdf)
        await db.commit()
        
        logger.info(f"세션에서 PDF 제거: {session_id} -> {pdf_id}")
        
        return {"message": "PDF가 세션에서 제거되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 제거 실패: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 제거 실패: {str(e)}")


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """채팅 세션 삭제"""
    try:
        # 세션 확인
        session = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = session.scalar_one_or_none()
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 세션 삭제 (관련 메시지와 PDF 연결도 자동 삭제됨)
        await db.delete(session)
        await db.commit()
        
        logger.info(f"채팅 세션 삭제: {session_id}")
        
        return {"message": "세션이 성공적으로 삭제되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"세션 삭제 실패: {str(e)}")


# ==================== WebSocket 지원 ====================

class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, session_id: str, message: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(message)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket을 통한 실시간 채팅"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # 질문 처리
            if message_data.get("type") == "question":
                question = message_data.get("content", "")
                
                # RAG 기반 답변 생성
                answer, sources = await rag_engine.generate_answer(question, [])
                
                # 응답 전송
                response = {
                    "type": "answer",
                    "content": answer,
                    "sources": [source.dict() for source in sources],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await websocket.send_text(json.dumps(response))
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        manager.disconnect(session_id)
