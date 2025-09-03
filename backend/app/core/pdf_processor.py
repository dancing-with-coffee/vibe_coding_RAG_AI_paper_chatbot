"""
PDF 프로세서
PDF 파일에서 텍스트를 추출하고 청킹하는 핵심 로직
"""

import pdfplumber
import PyPDF2
import fitz  # PyMuPDF
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF 파일 처리 및 텍스트 추출 클래스"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    async def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """PDF 파일 메타데이터 추출"""
        try:
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(
                self.executor, 
                self._extract_metadata_sync, 
                file_path
            )
            return metadata
        except Exception as e:
            logger.error(f"메타데이터 추출 실패: {e}")
            raise
    
    async def extract_text_chunks(self, file_path: str) -> List[Dict[str, Any]]:
        """PDF에서 텍스트 청크 추출"""
        try:
            loop = asyncio.get_event_loop()
            chunks = await loop.run_in_executor(
                self.executor, 
                self._extract_text_chunks_sync, 
                file_path
            )
            return chunks
        except Exception as e:
            logger.error(f"텍스트 청크 추출 실패: {e}")
            raise
    
    def _extract_metadata_sync(self, file_path: str) -> Dict[str, Any]:
        """동기적으로 메타데이터 추출"""
        try:
            metadata = {}
            
            # PyMuPDF로 기본 메타데이터 추출
            with fitz.open(file_path) as doc:
                metadata['page_count'] = len(doc)
                metadata['title'] = doc.metadata.get('title', '')
                metadata['author'] = doc.metadata.get('author', '')
                metadata['subject'] = doc.metadata.get('subject', '')
                metadata['creator'] = doc.metadata.get('creator', '')
                metadata['producer'] = doc.metadata.get('producer', '')
                metadata['creation_date'] = doc.metadata.get('creationDate', '')
                metadata['modification_date'] = doc.metadata.get('modDate', '')
                
                # 첫 페이지에서 제목 추출 시도
                if not metadata['title']:
                    first_page = doc[0]
                    text = first_page.get_text()
                    # 첫 번째 줄을 제목으로 간주
                    lines = text.strip().split('\n')
                    if lines:
                        metadata['title'] = lines[0][:100]  # 제목 길이 제한
            
            # pdfplumber로 추가 정보 추출
            try:
                with pdfplumber.open(file_path) as pdf:
                    # 텍스트 통계
                    total_chars = 0
                    total_words = 0
                    
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        total_chars += len(text)
                        total_words += len(text.split())
                    
                    metadata['total_characters'] = total_chars
                    metadata['total_words'] = total_words
                    metadata['average_chars_per_page'] = total_chars // metadata['page_count'] if metadata['page_count'] > 0 else 0
                    metadata['average_words_per_page'] = total_words // metadata['page_count'] if metadata['page_count'] > 0 else 0
                    
            except Exception as e:
                logger.warning(f"pdfplumber 메타데이터 추출 실패: {e}")
            
            # 파일 정보
            file_path_obj = Path(file_path)
            metadata['file_size'] = file_path_obj.stat().st_size
            metadata['file_extension'] = file_path_obj.suffix
            
            logger.info(f"메타데이터 추출 완료: {file_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"메타데이터 추출 실패: {e}")
            raise
    
    def _extract_text_chunks_sync(self, file_path: str) -> List[Dict[str, Any]]:
        """동기적으로 텍스트 청크 추출"""
        try:
            chunks = []
            
            # PyMuPDF로 텍스트 추출 (더 정확함)
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    
                    # 텍스트 추출
                    text = page.get_text()
                    
                    if not text.strip():
                        continue
                    
                    # 텍스트 정리
                    cleaned_text = self._clean_text(text)
                    
                    if not cleaned_text.strip():
                        continue
                    
                    # 청킹
                    page_chunks = self._create_chunks(
                        cleaned_text, 
                        page_num + 1, 
                        file_path
                    )
                    
                    chunks.extend(page_chunks)
            
            logger.info(f"텍스트 청크 추출 완료: {file_path} -> {len(chunks)}개 청크")
            return chunks
            
        except Exception as e:
            logger.error(f"텍스트 청크 추출 실패: {e}")
            raise
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리 및 전처리"""
        if not text:
            return ""
        
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 페이지 번호 제거 (일반적인 패턴)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        
        # 헤더/푸터 제거 (반복되는 패턴)
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 3:  # 너무 짧은 줄 제거
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _create_chunks(
        self, 
        text: str, 
        page_number: int, 
        file_path: str
    ) -> List[Dict[str, Any]]:
        """텍스트를 청크로 분할"""
        chunks = []
        
        if not text.strip():
            return chunks
        
        # 문단 단위로 분할
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        chunk_id = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 현재 청크에 문단 추가
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
            
            # 청크 크기 확인
            if len(current_chunk) >= self.chunk_size:
                # 청크 저장
                chunks.append({
                    'id': f"{Path(file_path).stem}_page{page_number}_chunk{chunk_id}",
                    'content': current_chunk,
                    'page_number': page_number,
                    'chunk_size': len(current_chunk),
                    'file_path': file_path,
                    'chunk_type': 'paragraph'
                })
                
                # 오버랩을 고려한 다음 청크 시작
                if self.chunk_overlap > 0:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text
                else:
                    current_chunk = ""
                
                chunk_id += 1
        
        # 마지막 청크 처리
        if current_chunk.strip():
            chunks.append({
                'id': f"{Path(file_path).stem}_page{page_number}_chunk{chunk_id}",
                'content': current_chunk,
                'page_number': page_number,
                'chunk_size': len(current_chunk),
                'file_path': file_path,
                'chunk_type': 'paragraph'
            })
        
        return chunks
    
    async def extract_text_by_page(self, file_path: str) -> Dict[int, str]:
        """페이지별로 텍스트 추출"""
        try:
            loop = asyncio.get_event_loop()
            page_texts = await loop.run_in_executor(
                self.executor, 
                self._extract_text_by_page_sync, 
                file_path
            )
            return page_texts
        except Exception as e:
            logger.error(f"페이지별 텍스트 추출 실패: {e}")
            raise
    
    def _extract_text_by_page_sync(self, file_path: str) -> Dict[int, str]:
        """동기적으로 페이지별 텍스트 추출"""
        try:
            page_texts = {}
            
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    
                    if text.strip():
                        page_texts[page_num + 1] = self._clean_text(text)
            
            return page_texts
            
        except Exception as e:
            logger.error(f"페이지별 텍스트 추출 실패: {e}")
            raise
    
    async def search_text_in_pdf(self, file_path: str, search_term: str) -> List[Dict[str, Any]]:
        """PDF에서 특정 텍스트 검색"""
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self.executor, 
                self._search_text_in_pdf_sync, 
                file_path, 
                search_term
            )
            return results
        except Exception as e:
            logger.error(f"텍스트 검색 실패: {e}")
            raise
    
    def _search_text_in_pdf_sync(self, file_path: str, search_term: str) -> List[Dict[str, Any]]:
        """동기적으로 텍스트 검색"""
        try:
            results = []
            
            with fitz.open(file_path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    
                    if search_term.lower() in text.lower():
                        # 검색어 주변 컨텍스트 추출
                        context = self._extract_context(text, search_term)
                        
                        results.append({
                            'page_number': page_num + 1,
                            'context': context,
                            'search_term': search_term,
                            'file_path': file_path
                        })
            
            return results
            
        except Exception as e:
            logger.error(f"텍스트 검색 실패: {e}")
            raise
    
    def _extract_context(self, text: str, search_term: str, context_size: int = 100) -> str:
        """검색어 주변 컨텍스트 추출"""
        try:
            # 검색어 위치 찾기
            term_lower = search_term.lower()
            text_lower = text.lower()
            
            if term_lower not in text_lower:
                return ""
            
            start_pos = text_lower.find(term_lower)
            
            # 컨텍스트 범위 계산
            context_start = max(0, start_pos - context_size)
            context_end = min(len(text), start_pos + len(search_term) + context_size)
            
            # 컨텍스트 추출
            context = text[context_start:context_end]
            
            # 문장 경계 조정
            if context_start > 0:
                # 첫 번째 완전한 단어부터 시작
                first_space = context.find(' ')
                if first_space != -1:
                    context = context[first_space + 1:]
            
            if context_end < len(text):
                # 마지막 완전한 단어까지
                last_space = context.rfind(' ')
                if last_space != -1:
                    context = context[:last_space]
            
            return context.strip()
            
        except Exception as e:
            logger.error(f"컨텍스트 추출 실패: {e}")
            return ""
    
    def __del__(self):
        """리소스 정리"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
