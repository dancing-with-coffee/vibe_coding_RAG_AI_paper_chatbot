import fitz  # PyMuPDF
import os
from typing import List, Dict
import re

class PDFProcessor:
    def __init__(self, pdf_directory: str):
        self.pdf_directory = pdf_directory
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트를 추출합니다."""
        try:
            print(f"  📖 처리 중: {os.path.basename(pdf_path)}")
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():  # 빈 페이지는 건너뛰기
                    text += page_text
                    
            doc.close()
            
            if not text.strip():
                print(f"  ⚠️  경고: {os.path.basename(pdf_path)}에서 텍스트를 추출할 수 없습니다.")
                return ""
                
            print(f"  ✅ {len(text)} 문자 추출 완료")
            return text

        except Exception as e:
            print(f"  ❌ PDF 처리 오류 {os.path.basename(pdf_path)}: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """텍스트를 정리합니다."""
        # 줄바꿈을 공백으로 변환
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        
        # 여러 공백을 하나로 줄이기
        text = re.sub(r'\s+', ' ', text)
        
        # 특수 문자는 유지하되 이상한 문자만 제거
        text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
        
        return text.strip()
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """텍스트를 청크로 나눕니다."""
        if not text or len(text) <= chunk_size:
            return [text] if text else []
        
        chunks = []
        sentences = self._split_into_sentences(text)
        current_chunk = ""
        
        for sentence in sentences:
            # 현재 청크 + 새 문장이 chunk_size를 초과하는 경우
            if len(current_chunk) + len(sentence) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # 오버랩을 위해 마지막 부분 유지
                    if len(current_chunk) > overlap:
                        current_chunk = current_chunk[-overlap:] + " " + sentence
                    else:
                        current_chunk = sentence
                else:
                    # 문장 하나가 chunk_size보다 긴 경우
                    chunks.append(sentence[:chunk_size])
                    current_chunk = sentence[chunk_size:]
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # 마지막 청크 추가
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할합니다."""
        # 문장 끝 패턴 (마침표, 느낌표, 물음표 뒤에 공백이나 문장 끝)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def process_all_pdfs(self) -> List[Dict]:
        """모든 PDF를 처리하여 청크로 나눕니다."""
        documents = []
        
        # PDF 파일 목록
        pdf_files = [f for f in os.listdir(self.pdf_directory) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            print(f"❌ {self.pdf_directory}에 PDF 파일이 없습니다.")
            return documents
        
        print(f"\n📚 {len(pdf_files)}개의 PDF 파일 처리 시작...")
        
        for idx, filename in enumerate(pdf_files, 1):
            pdf_path = os.path.join(self.pdf_directory, filename)
            print(f"\n[{idx}/{len(pdf_files)}] {filename}")
            
            # 텍스트 추출
            text = self.extract_text_from_pdf(pdf_path)
            if not text:
                continue
            
            # 텍스트 정리
            cleaned_text = self.clean_text(text)
            if not cleaned_text:
                print(f"  ⚠️  정리 후 빈 텍스트")
                continue
            
            # 청크 생성
            chunks = self.chunk_text(cleaned_text)
            print(f"  📄 {len(chunks)}개의 청크 생성")
            
            # 문서 리스트에 추가
            for i, chunk in enumerate(chunks):
                if chunk.strip():  # 빈 청크는 제외
                    documents.append({
                        'text': chunk,
                        'metadata': {
                            'filename': filename,
                            'chunk_id': i,
                            'total_chunks': len(chunks),
                            'source': pdf_path
                        }
                    })
        
        print(f"\n✅ 총 {len(documents)}개의 문서 청크가 생성되었습니다.")
        return documents