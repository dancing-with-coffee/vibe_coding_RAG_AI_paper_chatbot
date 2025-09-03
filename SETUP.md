# RAG Paper Chatbot 설정 가이드

## 🚀 빠른 시작

### 1. 환경 설정

#### 필수 요구사항
- Docker & Docker Compose
- Python 3.9+
- Node.js 18+
- OpenAI API 키

#### 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# OpenAI API 키 설정
echo "OPENAI_API_KEY=your_actual_api_key_here" >> .env
```

### 2. Docker로 실행 (권장)

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
docker-compose logs -f chromadb
```

#### 서비스 상태 확인
```bash
# 모든 서비스 상태
docker-compose ps

# 헬스체크
curl http://localhost:8001/health
curl http://localhost:3000
```

### 3. 개발 모드 실행

#### 백엔드 실행
```bash
cd backend

# 가상환경 생성 (선택사항)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
export OPENAI_API_KEY="your_api_key_here"
export DATABASE_URL="postgresql://rag_user:rag_password@localhost:5432/rag_paper_db"

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 프론트엔드 실행
```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

#### 데이터베이스 실행
```bash
# PostgreSQL만 실행
docker-compose up -d postgres

# ChromaDB만 실행
docker-compose up -d chromadb
```

## 🔧 상세 설정

### 데이터베이스 초기화
```bash
# PostgreSQL에 직접 연결
docker-compose exec postgres psql -U rag_user -d rag_paper_db

# 초기화 스크립트 실행
docker-compose exec postgres psql -U rag_user -d rag_paper_db -f /docker-entrypoint-initdb.d/init.sql
```

### ChromaDB 설정
```bash
# ChromaDB 상태 확인
curl http://localhost:8000/api/v1/heartbeat

# 컬렉션 정보 확인
curl http://localhost:8000/api/v1/collections
```

### API 테스트
```bash
# 헬스체크
curl http://localhost:8001/health

# API 문서
open http://localhost:8001/docs

# PDF 업로드 테스트
curl -X POST "http://localhost:8001/api/v1/pdf/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.pdf"
```

## 🐛 문제 해결

### 일반적인 문제들

#### 1. 포트 충돌
```bash
# 포트 사용 확인
lsof -i :8001
lsof -i :3000
lsof -i :5432
lsof -i :8000

# 충돌하는 프로세스 종료
kill -9 <PID>
```

#### 2. 데이터베이스 연결 실패
```bash
# PostgreSQL 상태 확인
docker-compose exec postgres pg_isready -U rag_user -d rag_paper_db

# 연결 테스트
docker-compose exec postgres psql -U rag_user -d rag_paper_db -c "SELECT 1;"
```

#### 3. ChromaDB 연결 실패
```bash
# ChromaDB 상태 확인
docker-compose exec chromadb curl -f http://localhost:8000/api/v1/heartbeat

# 로그 확인
docker-compose logs chromadb
```

#### 4. OpenAI API 오류
```bash
# API 키 확인
echo $OPENAI_API_KEY

# API 테스트
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

### 로그 분석

#### 백엔드 로그
```bash
# 실시간 로그
docker-compose logs -f backend

# 특정 시간대 로그
docker-compose logs --since="2024-01-01T00:00:00" backend

# 오류 로그만
docker-compose logs backend | grep ERROR
```

#### 프론트엔드 로그
```bash
# 브라우저 개발자 도구
# Console 탭에서 오류 확인
# Network 탭에서 API 요청/응답 확인
```

## 📊 모니터링

### 성능 지표
```bash
# API 응답 시간
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8001/health"

# 데이터베이스 성능
docker-compose exec postgres psql -U rag_user -d rag_paper_db -c "
SELECT 
  schemaname,
  tablename,
  attname,
  n_distinct,
  correlation
FROM pg_stats 
WHERE schemaname = 'public';"
```

### 리소스 사용량
```bash
# 컨테이너 리소스 사용량
docker stats

# 특정 컨테이너 상세 정보
docker-compose exec backend top
docker-compose exec postgres top
```

## 🔄 업데이트 및 배포

### 코드 업데이트
```bash
# Git에서 최신 코드 가져오기
git pull origin main

# Docker 이미지 재빌드
docker-compose build --no-cache

# 서비스 재시작
docker-compose up -d --force-recreate
```

### 데이터베이스 마이그레이션
```bash
# 백업 생성
docker-compose exec postgres pg_dump -U rag_user rag_paper_db > backup.sql

# 마이그레이션 실행
docker-compose exec postgres psql -U rag_user -d rag_paper_db -f migration.sql
```

### 환경 변수 업데이트
```bash
# .env 파일 수정 후
docker-compose down
docker-compose up -d
```

## 🧪 테스트

### 단위 테스트
```bash
cd backend
pytest tests/ -v

# 특정 테스트만 실행
pytest tests/test_pdf_processor.py -v
```

### 통합 테스트
```bash
# API 엔드포인트 테스트
curl -X POST "http://localhost:8001/api/v1/chat/session" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-001"}'
```

### 부하 테스트
```bash
# 간단한 부하 테스트
for i in {1..10}; do
  curl -s "http://localhost:8001/health" &
done
wait
```

## 📚 추가 리소스

### 문서
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [React 공식 문서](https://react.dev/)
- [ChromaDB 문서](https://docs.trychroma.com/)
- [OpenAI API 문서](https://platform.openai.com/docs)

### 유용한 명령어
```bash
# 전체 시스템 상태 확인
docker-compose ps && echo "---" && \
curl -s http://localhost:8001/health | jq . && echo "---" && \
curl -s http://localhost:8000/api/v1/heartbeat

# 로그 정리
docker-compose logs --tail=100 > logs.txt

# 시스템 정리
docker-compose down -v
docker system prune -f
```

## 🆘 지원

문제가 발생하면 다음을 확인하세요:

1. **로그 확인**: `docker-compose logs -f [service_name]`
2. **상태 확인**: `docker-compose ps`
3. **헬스체크**: 각 서비스의 헬스 엔드포인트 호출
4. **리소스 확인**: `docker stats`
5. **네트워크 확인**: `docker network ls` 및 `docker network inspect`

여전히 문제가 해결되지 않으면 GitHub Issues에 상세한 오류 로그와 함께 보고해주세요.
