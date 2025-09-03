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
    
    # 청크 설정
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200

settings = Settings()
