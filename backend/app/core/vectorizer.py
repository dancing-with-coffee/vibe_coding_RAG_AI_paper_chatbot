"""
벡터라이저
텍스트를 벡터화하고 ChromaDB에 저장하는 핵심 로직
"""

import chromadb
from chromadb.config import Settings
import openai
import logging
import asyncio
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class Vectorizer:
    """텍스트 벡터화 및 ChromaDB 관리 클래스"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.openai_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """클라이언트 초기화"""
        try:
            # ChromaDB 클라이언트 초기화
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=Settings(
                    chroma_api_impl="rest",
                    chroma_server_host=settings.CHROMA_HOST,
                    chroma_server_http_port=settings.CHROMA_PORT
                )
            )
            
            # 컬렉션 가져오기 또는 생성
            self.collection = self._get_or_create_collection()
            
            # OpenAI 클라이언트 초기화
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            logger.info("벡터라이저 클라이언트 초기화 완료")
            
        except Exception as e:
            logger.error(f"벡터라이저 클라이언트 초기화 실패: {e}")
            raise
    
    def _get_or_create_collection(self, collection_name: str = "paper_chunks"):
        """컬렉션 가져오기 또는 생성"""
        try:
            # 기존 컬렉션 확인
            collections = self.client.list_collections()
            
            if collection_name in [col.name for col in collections]:
                collection = self.client.get_collection(collection_name)
                logger.info(f"기존 컬렉션 사용: {collection_name}")
            else:
                # 새 컬렉션 생성
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"description": "논문 PDF 텍스트 청크 벡터 저장소"}
                )
                logger.info(f"새 컬렉션 생성: {collection_name}")
            
            return collection
            
        except Exception as e:
            logger.error(f"컬렉션 생성/가져오기 실패: {e}")
            raise
    
    async def vectorize_document(
        self, 
        pdf_id: str, 
        text_chunks: List[Dict[str, Any]], 
        metadata: Dict[str, Any]
    ) -> bool:
        """문서 벡터화 및 저장"""
        try:
            if not text_chunks:
                logger.warning(f"벡터화할 텍스트 청크가 없습니다: {pdf_id}")
                return False
            
            logger.info(f"문서 벡터화 시작: {pdf_id} -> {len(text_chunks)}개 청크")
            
            # 청크별로 벡터화 및 저장
            for i, chunk in enumerate(text_chunks):
                try:
                    # 임베딩 생성
                    embedding = await self._generate_embedding(chunk['content'])
                    
                    if not embedding:
                        logger.warning(f"임베딩 생성 실패: {chunk['id']}")
                        continue
                    
                    # 메타데이터 준비
                    chunk_metadata = {
                        'pdf_id': str(pdf_id),
                        'chunk_id': chunk['id'],
                        'page_number': chunk['page_number'],
                        'chunk_size': chunk['chunk_size'],
                        'chunk_type': chunk.get('chunk_type', 'paragraph'),
                        'file_path': chunk['file_path'],
                        'pdf_metadata': metadata,
                        'created_at': datetime.utcnow().isoformat()
                    }
                    
                    # ChromaDB에 저장
                    self.collection.add(
                        embeddings=[embedding],
                        documents=[chunk['content']],
                        metadatas=[chunk_metadata],
                        ids=[chunk['id']]
                    )
                    
                    logger.debug(f"청크 벡터화 완료: {chunk['id']}")
                    
                except Exception as e:
                    logger.error(f"청크 벡터화 실패: {chunk['id']} - {e}")
                    continue
            
            logger.info(f"문서 벡터화 완료: {pdf_id}")
            return True
            
        except Exception as e:
            logger.error(f"문서 벡터화 실패: {pdf_id} - {e}")
            return False
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """텍스트 임베딩 생성"""
        try:
            if not self.openai_client:
                logger.error("OpenAI 클라이언트가 초기화되지 않았습니다")
                return None
            
            # 텍스트 길이 제한 (토큰 제한 고려)
            max_length = 8000  # 안전한 길이
            if len(text) > max_length:
                text = text[:max_length]
            
            # OpenAI 임베딩 API 호출
            response = await self.openai_client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=text
            )
            
            embedding = response.data[0].embedding
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return None
    
    async def search_similar(
        self, 
        query: str, 
        pdf_ids: Optional[List[str]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """유사한 텍스트 청크 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = await self._generate_embedding(query)
            
            if not query_embedding:
                logger.error("쿼리 임베딩 생성 실패")
                return []
            
            # 검색 조건 설정
            where_clause = {}
            if pdf_ids:
                where_clause["pdf_id"] = {"$in": pdf_ids}
            
            # ChromaDB에서 검색
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 처리
            search_results = []
            if results['documents'] and results['documents'][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # 유사도 점수 계산 (거리를 유사도로 변환)
                    similarity_score = 1.0 - distance
                    
                    # 임계값 필터링
                    if similarity_score >= similarity_threshold:
                        search_results.append({
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': similarity_score,
                            'rank': i + 1
                        })
            
            logger.info(f"검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"유사도 검색 실패: {e}")
            return []
    
    async def get_document_chunks(self, pdf_id: str) -> List[Dict[str, Any]]:
        """특정 PDF의 모든 청크 조회"""
        try:
            results = self.collection.get(
                where={"pdf_id": pdf_id},
                include=["documents", "metadatas"]
            )
            
            chunks = []
            if results['documents']:
                for doc, metadata in zip(results['documents'], results['metadatas']):
                    chunks.append({
                        'content': doc,
                        'metadata': metadata
                    })
            
            logger.info(f"PDF 청크 조회 완료: {pdf_id} -> {len(chunks)}개")
            return chunks
            
        except Exception as e:
            logger.error(f"PDF 청크 조회 실패: {e}")
            return []
    
    async def delete_document(self, pdf_id: str) -> bool:
        """PDF 문서의 모든 벡터 데이터 삭제"""
        try:
            # PDF ID로 필터링하여 삭제
            self.collection.delete(
                where={"pdf_id": str(pdf_id)}
            )
            
            logger.info(f"PDF 벡터 데이터 삭제 완료: {pdf_id}")
            return True
            
        except Exception as e:
            logger.error(f"PDF 벡터 데이터 삭제 실패: {e}")
            return False
    
    async def update_document_metadata(
        self, 
        pdf_id: str, 
        new_metadata: Dict[str, Any]
    ) -> bool:
        """PDF 문서 메타데이터 업데이트"""
        try:
            # 기존 청크들의 메타데이터 업데이트
            chunks = await self.get_document_chunks(pdf_id)
            
            for chunk in chunks:
                chunk_id = chunk['metadata']['chunk_id']
                updated_metadata = chunk['metadata'].copy()
                updated_metadata['pdf_metadata'] = new_metadata
                updated_metadata['updated_at'] = datetime.utcnow().isoformat()
                
                # 메타데이터만 업데이트
                self.collection.update(
                    ids=[chunk_id],
                    metadatas=[updated_metadata]
                )
            
            logger.info(f"PDF 메타데이터 업데이트 완료: {pdf_id}")
            return True
            
        except Exception as e:
            logger.error(f"PDF 메타데이터 업데이트 실패: {e}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """컬렉션 통계 정보 조회"""
        try:
            count = self.collection.count()
            
            # PDF ID별 청크 수 계산
            pdf_counts = {}
            if count > 0:
                all_chunks = self.collection.get(include=["metadatas"])
                
                for metadata in all_chunks['metadatas']:
                    pdf_id = metadata['pdf_id']
                    pdf_counts[pdf_id] = pdf_counts.get(pdf_id, 0) + 1
            
            stats = {
                'total_chunks': count,
                'unique_pdfs': len(pdf_counts),
                'pdf_chunk_counts': pdf_counts,
                'collection_name': self.collection.name,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"컬렉션 통계 조회 실패: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """벡터라이저 상태 확인"""
        try:
            # ChromaDB 연결 확인
            collections = self.client.list_collections()
            
            # OpenAI 연결 확인 (간단한 테스트)
            if self.openai_client:
                test_embedding = await self._generate_embedding("test")
                if not test_embedding:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"벡터라이저 상태 확인 실패: {e}")
            return False
    
    def __del__(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
        except Exception as e:
            logger.error(f"벡터라이저 정리 실패: {e}")
