from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import os

from .pdf_processor import PDFProcessor
from .vector_store import VectorStore
from .rag_engine import RAGEngine
from .config import settings

app = FastAPI(title="AI Research Papers RAG Chatbot")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
rag_engine = None

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]

@app.on_event("startup")
async def startup_event():
    """서버 시작시 데이터 초기화"""
    global rag_engine
    
    print("RAG 엔진 초기화 중...")
    try:
        rag_engine = RAGEngine()
        print("RAG 엔진 초기화 완료")
        
        # 벡터 스토어가 비어있으면 PDF 처리 (비동기로 처리)
        print("벡터 스토어 상태 확인 중...")
        
    except Exception as e:
        print(f"RAG 엔진 초기화 중 오류: {e}")
        # 오류가 있어도 서버는 시작되도록 함
        rag_engine = None

async def initialize_vector_store():
    """PDF 파일들을 처리하여 벡터 스토어에 저장"""
    print("PDF 파일 처리 시작...")
    
    if not os.path.exists(settings.PDF_DIRECTORY):
        print(f"PDF 디렉토리를 찾을 수 없습니다: {settings.PDF_DIRECTORY}")
        return
    
    # PDF 처리
    processor = PDFProcessor(settings.PDF_DIRECTORY)
    documents = processor.process_all_pdfs()
    
    if documents:
        print(f"{len(documents)}개의 문서 청크 생성됨")
        rag_engine.vector_store.add_documents(documents)
        print("벡터 스토어 초기화 완료!")
    else:
        print("처리할 PDF 파일이 없습니다.")

@app.get("/")
async def root():
    return {"message": "AI Research Papers RAG Chatbot API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 메시지 처리"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")
    
    if not rag_engine:
        # RAG 엔진이 없으면 테스트 응답 반환
        return ChatResponse(
            answer="죄송합니다. RAG 시스템이 아직 초기화되지 않았습니다. OpenAI API 키를 확인하고 서버를 다시 시작해주세요.",
            sources=[]
        )
    
    try:
        response = rag_engine.generate_response(request.message)
        return ChatResponse(**response)
    except Exception as e:
        # 오류 시 안전한 응답 반환
        return ChatResponse(
            answer=f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
            sources=[]
        )

@app.post("/reset")
async def reset_vector_store():
    """벡터 스토어 초기화"""
    global rag_engine
    if rag_engine:
        rag_engine.vector_store.reset_collection()
        await initialize_vector_store()
        return {"message": "벡터 스토어가 초기화되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="RAG 엔진이 초기화되지 않았습니다.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
