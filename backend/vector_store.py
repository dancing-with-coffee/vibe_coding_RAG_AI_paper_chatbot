import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from typing import List, Dict
import os
import time
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
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 50) -> List[List[float]]:
        """배치 단위로 임베딩을 생성합니다."""
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        print(f"📊 총 {len(texts)}개 텍스트를 {total_batches}개 배치로 처리합니다.")
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"  배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 텍스트)")
            
            try:
                # 배치 임베딩 생성
                embeddings = self.get_embeddings(batch)
                all_embeddings.extend(embeddings)
                
                # API 제한을 피하기 위한 짧은 대기
                if batch_num < total_batches:
                    time.sleep(0.5)  # 0.5초 대기
                    
            except Exception as e:
                print(f"  ❌ 배치 {batch_num} 처리 실패: {e}")
                # 실패한 배치는 빈 임베딩으로 채우기
                all_embeddings.extend([[0.0] * 1536 for _ in batch])  # text-embedding-ada-002는 1536차원
        
        print(f"✅ 모든 배치 처리 완료! (총 {len(all_embeddings)}개 임베딩)")
        return all_embeddings
    
    def add_documents(self, documents: List[Dict]):
        """문서들을 벡터 스토어에 추가합니다."""
        if not documents:
            return
        
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
        try:
            # 텍스트 길이 확인 및 필터링
            filtered_docs = []
            filtered_texts = []
            filtered_metadatas = []
            
            print(f"📝 문서 필터링 중...")
            for i, (text, meta) in enumerate(zip(texts, metadatas)):
                # 너무 긴 텍스트는 잘라내기 (약 8000 토큰 제한, 문자로는 대략 30000자)
                if len(text) > 30000:
                    text = text[:30000]
                    print(f"  ⚠️  문서 {i+1} 길이 조정: {meta['filename']}")
                
                # 너무 짧은 텍스트는 제외
                if len(text.strip()) < 10:
                    print(f"  ⏭️  문서 {i+1} 건너뜀 (너무 짧음): {meta['filename']}")
                    continue
                
                filtered_texts.append(text)
                filtered_metadatas.append(meta)
            
            if not filtered_texts:
                print("❌ 유효한 문서가 없습니다.")
                return
            
            print(f"✅ {len(filtered_texts)}개의 유효한 문서 선택됨")
            
            # 배치 단위로 임베딩 생성
            print("🔄 임베딩 생성 중... (시간이 걸릴 수 있습니다)")
            embeddings = self.get_embeddings_batch(filtered_texts, batch_size=50)
            
            # 고유 ID 생성
            ids = [f"{meta['filename']}_{meta['chunk_id']}" for meta in filtered_metadatas]
            
            # ChromaDB에 배치로 추가
            batch_size = 100  # ChromaDB 배치 크기
            total_batches = (len(filtered_texts) + batch_size - 1) // batch_size
            
            print(f"💾 ChromaDB에 저장 중... (총 {total_batches}개 배치)")
            
            for i in range(0, len(filtered_texts), batch_size):
                batch_end = min(i + batch_size, len(filtered_texts))
                batch_num = i // batch_size + 1
                
                print(f"  배치 {batch_num}/{total_batches} 저장 중...")
                
                self.collection.add(
                    embeddings=embeddings[i:batch_end],
                    documents=filtered_texts[i:batch_end],
                    metadatas=filtered_metadatas[i:batch_end],
                    ids=ids[i:batch_end]
                )
            
            print(f"✅ {len(filtered_texts)}개 문서 청크가 성공적으로 추가되었습니다!")
            
        except Exception as e:
            print(f"문서 추가 중 오류: {e}")
            raise
    
    def search_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """유사한 문서를 검색합니다."""
        try:
            # 쿼리가 너무 길면 잘라내기
            if len(query) > 1000:
                query = query[:1000]
            
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
            print("✅ 컬렉션이 초기화되었습니다.")
        except Exception as e:
            print(f"컬렉션 초기화 중 오류: {e}")
            raise