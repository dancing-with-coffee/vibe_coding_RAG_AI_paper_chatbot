import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from typing import List, Dict
import os
from .config import settings

class VectorStore:
    def __init__(self):
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=ChromaSettings(allow_reset=True)
        )
        
        # OpenAI 클라이언트 초기화 - proxy 관련 설정 제거
        try:
            # API 키가 있는지 확인
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
            
            # 환경 변수에서 프록시 설정 제거 (있다면)
            for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
                if proxy_var in os.environ:
                    del os.environ[proxy_var]
            
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY
            )
        except Exception as e:
            print(f"OpenAI 클라이언트 초기화 오류: {e}")
            raise
        
        # 컬렉션 생성 또는 가져오기
        self.collection = self.client.get_or_create_collection(
            name="research_papers",
            metadata={"description": "AI Research Papers Collection"}
        )
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """OpenAI API를 사용하여 임베딩을 생성합니다."""
        try:
            response = self.openai_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            print(f"임베딩 생성 오류: {e}")
            raise
    
    def add_documents(self, documents: List[Dict]):
        """문서들을 벡터 스토어에 추가합니다."""
        if not documents:
            return
        
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
        try:
            # 임베딩 생성
            print("임베딩 생성 중...")
            embeddings = self.get_embeddings(texts)
            
            # 고유 ID 생성
            ids = [f"{meta['filename']}_{meta['chunk_id']}" for meta in metadatas]
            
            # ChromaDB에 추가
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"{len(documents)}개 문서 청크가 추가되었습니다.")
        except Exception as e:
            print(f"문서 추가 중 오류: {e}")
            raise
    
    def search_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """유사한 문서를 검색합니다."""
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.get_embeddings([query])[0]
            
            # 유사 문서 검색
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # 결과 포맷팅
            documents = []
            if results and results['documents'] and len(results['documents'][0]) > 0:
                for i in range(len(results['documents'][0])):
                    documents.append({
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i]
                    })
            
            return documents
        except Exception as e:
            print(f"문서 검색 중 오류: {e}")
            return []
    
    def reset_collection(self):
        """컬렉션을 초기화합니다."""
        try:
            self.client.reset()
            self.collection = self.client.get_or_create_collection(
                name="research_papers",
                metadata={"description": "AI Research Papers Collection"}
            )
        except Exception as e:
            print(f"컬렉션 초기화 중 오류: {e}")
            raise