-- RAG Paper Chatbot 데이터베이스 초기화 스크립트

-- 데이터베이스 생성 (이미 존재하는 경우 무시)
-- CREATE DATABASE rag_paper_db;

-- 사용자 생성 (이미 존재하는 경우 무시)
-- CREATE USER rag_user WITH PASSWORD 'rag_password';

-- 권한 부여
-- GRANT ALL PRIVILEGES ON DATABASE rag_paper_db TO rag_user;

-- 데이터베이스 연결
\c rag_paper_db;

-- 확장 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- PDF 문서 테이블
CREATE TABLE IF NOT EXISTS pdf_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    page_count INTEGER NOT NULL,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    vectorization_status VARCHAR(50) DEFAULT 'pending',
    vectorization_date TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 대화 세션 테이블
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 대화 메시지 테이블
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- PDF-세션 연결 테이블 (다중 PDF 지원)
CREATE TABLE IF NOT EXISTS session_pdfs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    pdf_id UUID REFERENCES pdf_documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, pdf_id)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_pdf_documents_filename ON pdf_documents(filename);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_status ON pdf_documents(vectorization_status);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_session_pdfs_session_id ON session_pdfs(session_id);
CREATE INDEX IF NOT EXISTS idx_session_pdfs_pdf_id ON session_pdfs(pdf_id);

-- 업데이트 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 트리거 생성
CREATE TRIGGER update_pdf_documents_updated_at 
    BEFORE UPDATE ON pdf_documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at 
    BEFORE UPDATE ON chat_sessions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 샘플 데이터 삽입 (개발용)
INSERT INTO chat_sessions (session_id) VALUES ('sample-session-001')
ON CONFLICT (session_id) DO NOTHING;

-- 뷰 생성 (자주 사용되는 쿼리를 위한 뷰)
CREATE OR REPLACE VIEW pdf_summary AS
SELECT 
    id,
    filename,
    original_filename,
    file_size,
    page_count,
    vectorization_status,
    upload_date,
    created_at
FROM pdf_documents
ORDER BY created_at DESC;

-- 권한 설정
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rag_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rag_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rag_user;

-- 테이블 정보 출력
\dt
\dv
