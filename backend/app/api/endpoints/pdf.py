"""
PDF 업로드 및 벡터화 API 엔드포인트
PDF 파일 업로드, 벡터화, 상태 확인을 처리합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import aiofiles
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional

from app.db.database import get_db
from app.models.schemas import (
    PDFDocumentCreate, PDFDocumentResponse, UploadResponse, 
    VectorizationStatus, PDFDocumentUpdate
)
from app.models.schemas import PDFDocument, ChatSession
from app.core.config import settings
from app.core.pdf_processor import PDFProcessor
from app.core.vectorizer import Vectorizer

router = APIRouter()
logger = logging.getLogger(__name__)

# PDF 프로세서 및 벡터라이저 인스턴스
pdf_processor = PDFProcessor()
vectorizer = Vectorizer()


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """PDF 파일 업로드 및 벡터화 시작"""
    
    # 파일 유효성 검사
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")
    
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"파일 크기는 {settings.MAX_FILE_SIZE // (1024*1024)}MB 이하여야 합니다"
        )
    
    try:
        # 고유한 파일명 생성
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        # 파일 저장
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # PDF 메타데이터 추출
        metadata = await pdf_processor.extract_metadata(file_path)
        page_count = metadata.get('page_count', 0)
        
        if page_count > settings.MAX_PAGES:
            # 파일 삭제
            os.remove(file_path)
            raise HTTPException(
                status_code=400, 
                detail=f"페이지 수는 {settings.MAX_PAGES}페이지 이하여야 합니다"
            )
        
        # 데이터베이스에 PDF 문서 정보 저장
        pdf_doc = PDFDocument(
            filename=unique_filename,
            original_filename=file.filename,
            file_size=file.size,
            page_count=page_count,
            metadata=metadata,
            vectorization_status="pending"
        )
        
        db.add(pdf_doc)
        await db.commit()
        await db.refresh(pdf_doc)
        
        # 백그라운드에서 벡터화 시작
        background_tasks.add_task(
            vectorize_pdf_background, 
            pdf_doc.id, 
            file_path, 
            metadata
        )
        
        logger.info(f"PDF 업로드 성공: {file.filename} -> {unique_filename}")
        
        return UploadResponse(
            message="PDF 업로드 성공. 벡터화가 진행 중입니다.",
            pdf_id=pdf_doc.id,
            filename=unique_filename,
            status="uploaded"
        )
        
    except Exception as e:
        logger.error(f"PDF 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"업로드 실패: {str(e)}")


@router.get("/list", response_model=List[PDFDocumentResponse])
async def list_pdfs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """업로드된 PDF 목록 조회"""
    try:
        query = select(PDFDocument).offset(skip).limit(limit).order_by(PDFDocument.created_at.desc())
        result = await db.execute(query)
        pdfs = result.scalars().all()
        
        return [PDFDocumentResponse.from_orm(pdf) for pdf in pdfs]
        
    except Exception as e:
        logger.error(f"PDF 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


@router.get("/{pdf_id}", response_model=PDFDocumentResponse)
async def get_pdf(
    pdf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """특정 PDF 정보 조회"""
    try:
        query = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(query)
        pdf = result.scalar_one_or_none()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF를 찾을 수 없습니다")
        
        return PDFDocumentResponse.from_orm(pdf)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


@router.get("/{pdf_id}/status", response_model=VectorizationStatus)
async def get_vectorization_status(
    pdf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """PDF 벡터화 상태 확인"""
    try:
        query = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(query)
        pdf = result.scalar_one_or_none()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF를 찾을 수 없습니다")
        
        return VectorizationStatus(
            pdf_id=pdf.id,
            status=pdf.vectorization_status,
            progress=get_vectorization_progress(pdf.vectorization_status),
            message=get_status_message(pdf.vectorization_status)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벡터화 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"조회 실패: {str(e)}")


@router.delete("/{pdf_id}")
async def delete_pdf(
    pdf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """PDF 삭제"""
    try:
        query = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(query)
        pdf = result.scalar_one_or_none()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF를 찾을 수 없습니다")
        
        # 파일 삭제
        file_path = os.path.join(settings.UPLOAD_DIR, pdf.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 벡터 데이터 삭제 (ChromaDB에서)
        try:
            await vectorizer.delete_document(pdf_id)
        except Exception as e:
            logger.warning(f"벡터 데이터 삭제 실패: {e}")
        
        # 데이터베이스에서 삭제
        await db.delete(pdf)
        await db.commit()
        
        logger.info(f"PDF 삭제 성공: {pdf.filename}")
        
        return {"message": "PDF가 성공적으로 삭제되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"삭제 실패: {str(e)}")


@router.post("/{pdf_id}/reprocess")
async def reprocess_pdf(
    pdf_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """PDF 재처리 (벡터화 재시작)"""
    try:
        query = select(PDFDocument).where(PDFDocument.id == pdf_id)
        result = await db.execute(query)
        pdf = result.scalar_one_or_none()
        
        if not pdf:
            raise HTTPException(status_code=404, detail="PDF를 찾을 수 없습니다")
        
        # 상태를 pending으로 변경
        pdf.vectorization_status = "pending"
        pdf.vectorization_date = None
        await db.commit()
        
        # 백그라운드에서 벡터화 재시작
        file_path = os.path.join(settings.UPLOAD_DIR, pdf.filename)
        metadata = pdf.metadata or {}
        
        background_tasks.add_task(
            vectorize_pdf_background, 
            pdf.id, 
            file_path, 
            metadata
        )
        
        logger.info(f"PDF 재처리 시작: {pdf.filename}")
        
        return {"message": "PDF 재처리가 시작되었습니다"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 재처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"재처리 실패: {str(e)}")


# ==================== 백그라운드 작업 ====================

async def vectorize_pdf_background(pdf_id: uuid.UUID, file_path: str, metadata: dict):
    """백그라운드에서 PDF 벡터화 수행"""
    try:
        logger.info(f"벡터화 시작: {pdf_id}")
        
        # PDF 텍스트 추출
        text_chunks = await pdf_processor.extract_text_chunks(file_path)
        
        # 벡터화 수행
        await vectorizer.vectorize_document(pdf_id, text_chunks, metadata)
        
        # 상태 업데이트
        async with get_db() as db:
            query = select(PDFDocument).where(PDFDocument.id == pdf_id)
            result = await db.execute(query)
            pdf = result.scalar_one_or_none()
            
            if pdf:
                pdf.vectorization_status = "completed"
                pdf.vectorization_date = datetime.utcnow()
                await db.commit()
                logger.info(f"벡터화 완료: {pdf_id}")
            else:
                logger.error(f"PDF를 찾을 수 없음: {pdf_id}")
                
    except Exception as e:
        logger.error(f"벡터화 실패: {pdf_id} - {e}")
        
        # 상태를 failed로 업데이트
        try:
            async with get_db() as db:
                query = select(PDFDocument).where(PDFDocument.id == pdf_id)
                result = await db.execute(query)
                pdf = result.scalar_one_or_none()
                
                if pdf:
                    pdf.vectorization_status = "failed"
                    await db.commit()
        except Exception as update_error:
            logger.error(f"상태 업데이트 실패: {update_error}")


# ==================== 유틸리티 함수 ====================

def get_vectorization_progress(status: str) -> Optional[float]:
    """벡터화 진행률 반환"""
    progress_map = {
        "pending": 0.0,
        "processing": 50.0,
        "completed": 100.0,
        "failed": 0.0
    }
    return progress_map.get(status, 0.0)


def get_status_message(status: str) -> str:
    """상태별 메시지 반환"""
    message_map = {
        "pending": "벡터화 대기 중",
        "processing": "벡터화 진행 중",
        "completed": "벡터화 완료",
        "failed": "벡터화 실패"
    }
    return message_map.get(status, "알 수 없는 상태")
