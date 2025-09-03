from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import os
import asyncio

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
initialization_complete = False

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]

def initialize_vector_store():
    """PDF 파일들을 처리하여 벡터 스토어에 저장 (동기 함수)"""
    global rag_engine, initialization_complete
    
    try:
        print("="*50)
        print("PDF 파일 처리 시작...")
        print("="*50)
        
        # PDF 디렉토리 확인
        if not os.path.exists(settings.PDF_DIRECTORY):
            print(f"❌ PDF 디렉토리를 찾을 수 없습니다: {settings.PDF_DIRECTORY}")
            os.makedirs(settings.PDF_DIRECTORY, exist_ok=True)
            print(f"✅ PDF 디렉토리를 생성했습니다: {settings.PDF_DIRECTORY}")
            print("📁 이 폴더에 PDF 파일을 추가한 후 서버를 재시작하세요.")
            return False
        
        # PDF 파일 목록 확인
        pdf_files = [f for f in os.listdir(settings.PDF_DIRECTORY) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"❌ {settings.PDF_DIRECTORY} 폴더에 PDF 파일이 없습니다.")
            print("📁 PDF 파일을 추가한 후 서버를 재시작하세요.")
            return False
        
        print(f"✅ {len(pdf_files)}개의 PDF 파일을 찾았습니다:")
        for pdf in pdf_files[:5]:  # 처음 5개만 출력
            print(f"   📄 {pdf}")
        if len(pdf_files) > 5:
            print(f"   ... 그 외 {len(pdf_files) - 5}개")
        
        # PDF 처리
        processor = PDFProcessor(settings.PDF_DIRECTORY)
        documents = processor.process_all_pdfs()
        
        if documents:
            print(f"✅ {len(documents)}개의 문서 청크가 생성되었습니다.")
            
            # 벡터 스토어에 추가
            print("🔄 벡터 임베딩 생성 중... (시간이 걸릴 수 있습니다)")
            rag_engine.vector_store.add_documents(documents)
            
            print("="*50)
            print("✅ 벡터 스토어 초기화 완료!")
            print("="*50)
            initialization_complete = True
            return True
        else:
            print("❌ PDF에서 텍스트를 추출할 수 없습니다.")
            return False
            
    except Exception as e:
        print(f"❌ 벡터 스토어 초기화 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.on_event("startup")
async def startup_event():
    """서버 시작시 데이터 초기화"""
    global rag_engine, initialization_complete
    
    print("\n" + "="*50)
    print("🚀 RAG 챗봇 서버 시작")
    print("="*50)
    
    # OpenAI API 키 확인
    if not settings.OPENAI_API_KEY:
        print("❌ OpenAI API 키가 설정되지 않았습니다!")
        print("📝 .env 파일에 OPENAI_API_KEY를 추가하세요.")
        return
    
    print("✅ OpenAI API 키가 설정되었습니다.")
    
    try:
        # RAG 엔진 초기화
        print("🔄 RAG 엔진 초기화 중...")
        rag_engine = RAGEngine()
        print("✅ RAG 엔진 초기화 완료")
        
        # 기존 벡터 스토어 확인
        try:
            test_result = rag_engine.vector_store.search_similar("test", n_results=1)
            if test_result:
                print("✅ 기존 벡터 스토어를 사용합니다.")
                initialization_complete = True
            else:
                print("📄 벡터 스토어가 비어있습니다. PDF 파일을 처리합니다...")
                asyncio.create_task(async_initialize())
        except:
            print("📄 새로운 벡터 스토어를 생성합니다...")
            asyncio.create_task(async_initialize())
            
    except Exception as e:
        print(f"❌ RAG 엔진 초기화 중 오류: {e}")
        import traceback
        traceback.print_exc()
        rag_engine = None

async def async_initialize():
    """비동기적으로 벡터 스토어 초기화"""
    await asyncio.sleep(1)  # 서버 시작을 기다림
    initialize_vector_store()

@app.get("/")
async def root():
    return {
        "message": "AI Research Papers RAG Chatbot API",
        "status": "ready" if initialization_complete else "initializing",
        "vector_store_ready": initialization_complete
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "rag_engine_ready": rag_engine is not None,
        "vector_store_ready": initialization_complete
    }

@app.get("/status")
async def get_status():
    """시스템 상태 확인"""
    status = {
        "rag_engine": rag_engine is not None,
        "vector_store": initialization_complete,
        "pdf_directory": os.path.exists(settings.PDF_DIRECTORY),
        "pdf_count": 0
    }
    
    if os.path.exists(settings.PDF_DIRECTORY):
        pdf_files = [f for f in os.listdir(settings.PDF_DIRECTORY) if f.lower().endswith('.pdf')]
        status["pdf_count"] = len(pdf_files)
        status["pdf_files"] = pdf_files[:10]  # 처음 10개만
    
    return status

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """채팅 메시지 처리"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")
    
    if not rag_engine:
        return ChatResponse(
            answer="죄송합니다. RAG 시스템이 아직 초기화되지 않았습니다. 잠시 후 다시 시도해주세요.",
            sources=[]
        )
    
    if not initialization_complete:
        return ChatResponse(
            answer="시스템이 초기화 중입니다. PDF 파일을 처리하고 있으니 잠시만 기다려주세요.",
            sources=[]
        )
    
    try:
        print(f"\n📨 질문 받음: {request.message}")
        response = rag_engine.generate_response(request.message)
        print(f"✅ 답변 생성 완료")
        return ChatResponse(**response)
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return ChatResponse(
            answer=f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
            sources=[]
        )

@app.post("/reset")
async def reset_vector_store():
    """벡터 스토어 초기화 및 PDF 재처리"""
    global rag_engine, initialization_complete
    
    if not rag_engine:
        raise HTTPException(status_code=500, detail="RAG 엔진이 초기화되지 않았습니다.")
    
    try:
        print("\n🔄 벡터 스토어 리셋 시작...")
        
        # 벡터 스토어 초기화
        rag_engine.vector_store.reset_collection()
        initialization_complete = False
        
        # PDF 재처리
        success = initialize_vector_store()
        
        if success:
            return {"message": "벡터 스토어가 성공적으로 초기화되었습니다.", "success": True}
        else:
            return {"message": "벡터 스토어 초기화 중 문제가 발생했습니다.", "success": False}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"초기화 중 오류: {str(e)}")

@app.post("/process-pdfs")
async def process_pdfs():
    """PDF 파일 수동 처리"""
    global initialization_complete
    
    if not rag_engine:
        raise HTTPException(status_code=500, detail="RAG 엔진이 초기화되지 않았습니다.")
    
    success = initialize_vector_store()
    
    if success:
        return {"message": "PDF 파일이 성공적으로 처리되었습니다.", "success": True}
    else:
        return {"message": "PDF 처리 중 문제가 발생했습니다.", "success": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)