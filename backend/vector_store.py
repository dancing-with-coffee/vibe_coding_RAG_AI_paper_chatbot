import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI
from typing import List, Dict
from .config import settings

class VectorStore:
    def __init__(self):
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=ChromaSettings(allow_reset=True)
        )
        
        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # 컬렉션 생성 또는 가져오기
        self.collection = self.client.get_or_create_collection(
            name="research_papers",
            metadata={"description": "AI Research Papers Collection"}
        )
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """OpenAI API를 사용하여 임베딩을 생성합니다."""
        response = self.openai_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts
        )
        return [embedding.embedding for embedding in response.data]
    
    def add_documents(self, documents: List[Dict]):
        """문서들을 벡터 스토어에 추가합니다."""
        if not documents:
            return
        
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
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
    
    def search_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """유사한 문서를 검색합니다."""
        # 쿼리 임베딩 생성
        query_embedding = self.get_embeddings([query])[0]
        
        # 유사 문서 검색
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # 결과 포맷팅
        documents = []
        for i in range(len(results['documents'][0])):
            documents.append({
                'text': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            })
        
        return documents
    
    def reset_collection(self):
        """컬렉션을 초기화합니다."""
        self.client.reset()
        self.collection = self.client.get_or_create_collection(
            name="research_papers",
            metadata={"description": "AI Research Papers Collection"}
        )
