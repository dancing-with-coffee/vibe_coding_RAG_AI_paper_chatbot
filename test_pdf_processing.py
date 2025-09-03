#!/usr/bin/env python3
"""
PDF 처리 테스트 스크립트
RAG 시스템이 PDF를 제대로 읽고 있는지 확인합니다.
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import settings
from backend.pdf_processor import PDFProcessor
from backend.vector_store import VectorStore

def test_pdf_directory():
    """PDF 디렉토리 확인"""
    print("="*50)
    print("1. PDF 디렉토리 확인")
    print("="*50)
    
    if not os.path.exists(settings.PDF_DIRECTORY):
        print(f"❌ 디렉토리가 없습니다: {settings.PDF_DIRECTORY}")
        print(f"📁 디렉토리를 생성합니다...")
        os.makedirs(settings.PDF_DIRECTORY, exist_ok=True)
        return False
    
    print(f"✅ 디렉토리 존재: {settings.PDF_DIRECTORY}")
    
    # PDF 파일 목록
    pdf_files = [f for f in os.listdir(settings.PDF_DIRECTORY) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"❌ PDF 파일이 없습니다!")
        print(f"📁 {settings.PDF_DIRECTORY} 폴더에 PDF 파일을 추가하세요.")
        return False
    
    print(f"✅ {len(pdf_files)}개의 PDF 파일 발견:")
    for pdf in pdf_files:
        size = os.path.getsize(os.path.join(settings.PDF_DIRECTORY, pdf))
        print(f"   📄 {pdf} ({size:,} bytes)")
    
    return True

def test_pdf_processing():
    """PDF 처리 테스트"""
    print("\n" + "="*50)
    print("2. PDF 텍스트 추출 테스트")
    print("="*50)
    
    processor = PDFProcessor(settings.PDF_DIRECTORY)
    documents = processor.process_all_pdfs()
    
    if not documents:
        print("❌ 문서가 생성되지 않았습니다!")
        return False
    
    print(f"\n✅ {len(documents)}개의 문서 청크 생성됨")
    
    # 첫 번째 청크 샘플 출력
    if documents:
        print("\n📋 첫 번째 청크 샘플:")
        print("-"*40)
        sample = documents[0]
        print(f"파일: {sample['metadata']['filename']}")
        print(f"청크 ID: {sample['metadata']['chunk_id']}")
        print(f"텍스트 (처음 200자):\n{sample['text'][:200]}...")
        print("-"*40)
    
    return documents

def test_vector_store(documents):
    """벡터 스토어 테스트"""
    print("\n" + "="*50)
    print("3. 벡터 스토어 테스트")
    print("="*50)
    
    try:
        # API 키 확인
        if not settings.OPENAI_API_KEY:
            print("❌ OpenAI API 키가 설정되지 않았습니다!")
            print("📝 .env 파일에 OPENAI_API_KEY를 추가하세요.")
            return False
        
        print("✅ OpenAI API 키 확인됨")
        
        # 벡터 스토어 초기화
        print("🔄 벡터 스토어 초기화 중...")
        vector_store = VectorStore()
        
        # 기존 데이터 삭제
        print("🗑️  기존 데이터 삭제...")
        vector_store.reset_collection()
        
        # 문서 추가 (처음 5개만 테스트)
        test_docs = documents[:5]
        print(f"📝 {len(test_docs)}개의 테스트 문서 추가 중...")
        vector_store.add_documents(test_docs)
        
        # 검색 테스트
        test_query = "AI"
        print(f"\n🔍 검색 테스트: '{test_query}'")
        results = vector_store.search_similar(test_query, n_results=3)
        
        if results:
            print(f"✅ {len(results)}개의 결과 찾음:")
            for i, result in enumerate(results, 1):
                print(f"\n결과 {i}:")
                print(f"  파일: {result['metadata']['filename']}")
                print(f"  거리: {result['distance']:.4f}")
                print(f"  텍스트 (처음 100자): {result['text'][:100]}...")
        else:
            print("❌ 검색 결과가 없습니다!")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("\n" + "="*50)
    print("🧪 PDF RAG 시스템 테스트")
    print("="*50)
    
    # 1. PDF 디렉토리 확인
    if not test_pdf_directory():
        print("\n❌ 테스트 실패: PDF 파일이 없습니다.")
        return
    
    # 2. PDF 처리
    documents = test_pdf_processing()
    if not documents:
        print("\n❌ 테스트 실패: PDF 처리 실패")
        return
    
    # 3. 벡터 스토어 테스트
    print("\n벡터 스토어를 테스트하시겠습니까? (OpenAI API 호출 발생)")
    response = input("계속하려면 'y'를 입력하세요: ")
    
    if response.lower() == 'y':
        if test_vector_store(documents):
            print("\n" + "="*50)
            print("✅ 모든 테스트 통과!")
            print("="*50)
        else:
            print("\n❌ 벡터 스토어 테스트 실패")
    else:
        print("\n⏭️  벡터 스토어 테스트를 건너뜁니다.")
        print("\n✅ PDF 처리 테스트 완료!")

if __name__ == "__main__":
    main()