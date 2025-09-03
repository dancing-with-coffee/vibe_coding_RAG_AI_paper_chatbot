# Vibe Coding RAG AI Paper Chatbot

논문 PDF를 업로드하면 RAG 기반 챗봇이 질문-답변을 제공하고 출처를 명확히 보여주는 웹 애플리케이션입니다.

## 🚀 주요 기능

- PDF 업로드 및 자동 벡터화
- RAG 기반 질문-답변 인터페이스
- 답변에 인용 문장 및 페이지 번호 표시
- 대화 히스토리 로컬 저장
- 다중 PDF 동시 질의 지원

## 🛠️ 기술 스택

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI + Python
- **Vector DB**: ChromaDB
- **Database**: PostgreSQL
- **LLM**: OpenAI API
- **Container**: Docker Compose

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 저장소 클론
git clone <repository-url>
cd vibe_coding_RAG_AI_paper_chatbot

# 환경 변수 설정
cp .env.example .env
# .env 파일에 OpenAI API 키 설정
```

### 2. Docker로 실행
```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 3. 개발 모드 실행
```bash
# 백엔드 실행
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 프론트엔드 실행 (새 터미널)
cd frontend
npm install
npm run dev
```

## 📁 프로젝트 구조

```
/
├── frontend/          # React 프론트엔드
├── backend/           # FastAPI 백엔드
├── docker-compose.yml # Docker 설정
└── README.md
```

## 🎯 MVP 목표

- [x] 프로젝트 구조 설정
- [ ] PDF 업로드 및 벡터화
- [ ] 챗 UI 및 Q&A API
- [ ] 인용 표시 및 히스토리
- [ ] 다중 PDF 지원
- [ ] 배포 및 테스트

## 📊 성능 목표

- PDF 업로드 성공률: 95% 이상
- 벡터화 완료: 1분 내 (5MB 기준)
- 답변 응답: 5초 내
- 답변 신뢰도: 4/5점 이상

## 🔧 개발 환경

- Python 3.9+
- Node.js 18+
- Docker & Docker Compose
- OpenAI API 키

## 📝 라이선스

MIT License
