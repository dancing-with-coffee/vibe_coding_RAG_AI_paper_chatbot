# AI Research Papers RAG Chatbot 🤖📚

AI 연구 논문을 기반으로 질문에 답변하는 RAG(Retrieval-Augmented Generation) 챗봇입니다.

## 🛠️ 기술 스택

- **백엔드**: FastAPI + Python
- **프론트엔드**: React + TypeScript + Vite
- **벡터 DB**: ChromaDB
- **LLM**: OpenAI GPT-3.5-turbo
- **임베딩**: OpenAI Embeddings
- **PDF 처리**: PyMuPDF

## 📋 사전 준비

1. **Python 3.8+** 설치
2. **Node.js 16+** 설치  
3. **OpenAI API 키** 준비

## ⚡ 빠른 시작

### 1. 의존성 설치

```bash
# Python 의존성 설치
pip install -r requirements.txt

# Node.js 의존성 설치  
npm install
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 추가하세요:

```bash
cp .env.example .env
# .env 파일을 열어서 실제 API 키로 변경
OPENAI_API_KEY=your_actual_openai_api_key_here
```

### 3. 서버 실행

**터미널 1: 백엔드 서버**
```bash
python run_backend.py
```

**터미널 2: 프론트엔드 서버**
```bash
npm run dev
```

### 4. 접속

- **챗봇 UI**: http://localhost:3000
- **API 문서**: http://localhost:8000/docs

## 📖 사용법

1. 브라우저에서 http://localhost:3000 접속
2. AI 연구 논문에 대한 질문 입력
3. RAG 시스템이 관련 논문 내용을 찾아서 답변 제공
4. 답변과 함께 참고한 논문 목록도 표시

## 🔍 예시 질문

- "Transformer 아키텍처의 주요 특징은 무엇인가요?"
- "RLHF와 RLAIF의 차이점을 설명해주세요"
- "LLaMA 모델의 특징은 무엇인가요?"
- "Constitutional AI는 어떤 방법론인가요?"

## 📁 프로젝트 구조

```
/
├── backend/              # FastAPI 백엔드
│   ├── main.py          # 메인 서버
│   ├── config.py        # 설정
│   ├── pdf_processor.py # PDF 처리
│   ├── vector_store.py  # ChromaDB 연동
│   └── rag_engine.py    # RAG 엔진
├── src/                 # React 프론트엔드
│   ├── App.tsx         # 메인 컴포넌트
│   └── App.css         # 스타일
├── AI research papers/  # PDF 논문 파일들
├── requirements.txt     # Python 의존성
├── package.json        # Node.js 의존성
└── run_backend.py      # 백엔드 실행 스크립트
```

## 🔧 개발 정보

- **첫 실행시** PDF 파일들이 자동으로 벡터 임베딩으로 변환됩니다
- **ChromaDB 데이터**는 `./chroma_db` 폴더에 저장됩니다
- **API 엔드포인트**: `/chat`, `/health`, `/reset`

## 🚨 문제 해결

1. **OpenAI API 오류**: `.env` 파일의 API 키 확인
2. **포트 충돌**: 8000(백엔드), 3000(프론트엔드) 포트 사용 중인지 확인
3. **PDF 처리 오류**: `AI research papers` 폴더에 PDF 파일이 있는지 확인

## 📝 라이선스

MIT License
