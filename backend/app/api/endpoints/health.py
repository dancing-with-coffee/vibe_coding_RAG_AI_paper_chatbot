"""
헬스 체크 API 엔드포인트
시스템 상태와 각 서비스의 상태를 확인합니다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging
import httpx
import asyncio

from app.db.database import get_db, health_check_db
from app.core.config import settings
from app.models.schemas import HealthCheck

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=HealthCheck)
async def health_check():
    """기본 헬스 체크"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        services={
            "api": "healthy",
            "database": "unknown",
            "chromadb": "unknown"
        }
    )


@router.get("/detailed", response_model=HealthCheck)
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """상세 헬스 체크 - 모든 서비스 상태 확인"""
    services_status = {}
    
    # API 상태
    services_status["api"] = "healthy"
    
    # 데이터베이스 상태
    try:
        db_healthy = await health_check_db()
        services_status["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services_status["database"] = "unhealthy"
    
    # ChromaDB 상태
    try:
        chroma_healthy = await check_chromadb_health()
        services_status["chromadb"] = "healthy" if chroma_healthy else "unhealthy"
    except Exception as e:
        logger.error(f"ChromaDB health check failed: {e}")
        services_status["chromadb"] = "unhealthy"
    
    # 전체 상태 결정
    overall_status = "healthy"
    if any(status == "unhealthy" for status in services_status.values()):
        overall_status = "degraded"
    if all(status == "unhealthy" for status in services_status.values()):
        overall_status = "unhealthy"
    
    return HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=services_status
    )


@router.get("/database")
async def database_health_check(db: AsyncSession = Depends(get_db)):
    """데이터베이스 전용 헬스 체크"""
    try:
        is_healthy = await health_check_db()
        if is_healthy:
            return {"status": "healthy", "message": "Database connection successful"}
        else:
            raise HTTPException(status_code=503, detail="Database connection failed")
    except Exception as e:
        logger.error(f"Database health check error: {e}")
        raise HTTPException(status_code=503, detail=f"Database health check failed: {str(e)}")


@router.get("/chromadb")
async def chromadb_health_check():
    """ChromaDB 전용 헬스 체크"""
    try:
        is_healthy = await check_chromadb_health()
        if is_healthy:
            return {"status": "healthy", "message": "ChromaDB connection successful"}
        else:
            raise HTTPException(status_code=503, detail="ChromaDB connection failed")
    except Exception as e:
        logger.error(f"ChromaDB health check error: {e}")
        raise HTTPException(status_code=503, detail=f"ChromaDB health check failed: {str(e)}")


async def check_chromadb_health() -> bool:
    """ChromaDB 연결 상태 확인"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.CHROMA_URL}/api/v1/heartbeat")
            return response.status_code == 200
    except Exception as e:
        logger.error(f"ChromaDB health check failed: {e}")
        return False


@router.get("/ready")
async def readiness_check():
    """애플리케이션 준비 상태 확인 (Kubernetes 등에서 사용)"""
    try:
        # 모든 필수 서비스 상태 확인
        db_ready = await health_check_db()
        chroma_ready = await check_chromadb_health()
        
        if db_ready and chroma_ready:
            return {"status": "ready", "message": "All services are ready"}
        else:
            raise HTTPException(
                status_code=503, 
                detail="Some services are not ready"
            )
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Readiness check failed: {str(e)}")


@router.get("/live")
async def liveness_check():
    """애플리케이션 생존 상태 확인 (Kubernetes 등에서 사용)"""
    return {"status": "alive", "timestamp": datetime.utcnow()}


# 백그라운드 헬스 체크 태스크
async def background_health_check():
    """백그라운드에서 주기적으로 헬스 체크 수행"""
    while True:
        try:
            logger.info("Performing background health check...")
            
            # 데이터베이스 상태 확인
            db_healthy = await health_check_db()
            logger.info(f"Database health: {'healthy' if db_healthy else 'unhealthy'}")
            
            # ChromaDB 상태 확인
            chroma_healthy = await check_chromadb_health()
            logger.info(f"ChromaDB health: {'healthy' if chroma_healthy else 'unhealthy'}")
            
            # 30초 대기
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Background health check failed: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 대기
