import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CHROMA_PERSIST_DIRECTORY = "./chroma_db"
    PDF_DIRECTORY = "./AI research papers"
    
    # OpenAI 설정
    EMBEDDING_MODEL = "text-embedding-ada-002"
    CHAT_MODEL = "gpt-3.5-turbo"
    
    # 청크 설정 - 크기를 줄여서 토큰 제한을 피함
    CHUNK_SIZE = 800  # 1000에서 800으로 줄임
    CHUNK_OVERLAP = 100  # 200에서 100으로 줄임
    
    # 배치 설정
    EMBEDDING_BATCH_SIZE = 50  # 한 번에 처리할 텍스트 수
    CHROMADB_BATCH_SIZE = 100  # ChromaDB에 한 번에 저장할 문서 수

settings = Settings()