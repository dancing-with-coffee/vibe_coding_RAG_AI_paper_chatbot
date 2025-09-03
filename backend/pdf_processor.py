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
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            print(f"PDF 처리 오류 {pdf_path}: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """텍스트를 정리합니다."""
        # 여러 공백을 하나로 줄이기
        text = re.sub(r'\s+', ' ', text)
        # 특수 문자 정리
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', ' ', text)
        return text.strip()
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """텍스트를 청크로 나눕니다."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            if end > len(text):
                end = len(text)
            
            # 문장 끝에서 자르기 시도
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period > start + chunk_size // 2:
                    end = last_period + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def process_all_pdfs(self) -> List[Dict]:
        """모든 PDF를 처리하여 청크로 나눕니다."""
        documents = []
        
        for filename in os.listdir(self.pdf_directory):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(self.pdf_directory, filename)
                print(f"처리 중: {filename}")
                
                text = self.extract_text_from_pdf(pdf_path)
                if not text:
                    continue
                
                cleaned_text = self.clean_text(text)
                chunks = self.chunk_text(cleaned_text)
                
                for i, chunk in enumerate(chunks):
                    documents.append({
                        'text': chunk,
                        'metadata': {
                            'filename': filename,
                            'chunk_id': i,
                            'total_chunks': len(chunks)
                        }
                    })
        
        return documents
