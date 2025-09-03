"""
데이터베이스 연결 및 세션 관리
PostgreSQL 데이터베이스와의 연결을 관리합니다.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker
import logging
from typing import AsyncGenerator

from app.core.config import settings

# 로깅 설정
logger = logging.getLogger(__name__)

# 데이터베이스 URL을 async 형식으로 변환
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# 비동기 엔진 생성
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
    max_overflow=20,
    pool_size=10
)

# 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 동기 엔진 (마이그레이션용)
sync_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG
)

# 베이스 클래스
Base = declarative_base()

# 메타데이터
metadata = MetaData()


async def init_db():
    """데이터베이스 초기화"""
    try:
        async with engine.begin() as conn:
            # 테이블 생성
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """데이터베이스 세션 의존성"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def close_db():
    """데이터베이스 연결 종료"""
    try:
        await engine.dispose()
        logger.info("✅ Database connections closed successfully")
    except Exception as e:
        logger.error(f"❌ Database connection closure failed: {e}")


async def health_check_db() -> bool:
    """데이터베이스 연결 상태 확인"""
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# 데이터베이스 연결 테스트
async def test_connection():
    """데이터베이스 연결 테스트"""
    try:
        async with engine.begin() as conn:
            result = await conn.execute("SELECT version()")
            version = result.scalar()
            logger.info(f"✅ Database connected successfully: {version}")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # 연결 테스트
    asyncio.run(test_connection())
