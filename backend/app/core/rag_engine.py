"""
RAG 엔진
Retrieval-Augmented Generation 기반 질문-답변 생성 엔진
"""

import openai
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from app.core.config import settings
from app.core.vectorizer import Vectorizer
from app.models.schemas import SourceInfo

logger = logging.getLogger(__name__)


class RAGEngine:
    """RAG 기반 질문-답변 생성 엔진"""
    
    def __init__(self):
        self.vectorizer = Vectorizer()
        self.openai_client = None
        self._initialize_openai()
    
    def _initialize_openai(self):
        """OpenAI 클라이언트 초기화"""
        try:
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI 클라이언트 초기화 완료")
            else:
                logger.warning("OpenAI API 키가 설정되지 않았습니다")
        except Exception as e:
            logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
    
    async def generate_answer(
        self, 
        question: str, 
        pdf_ids: Optional[List[str]] = None,
        max_sources: int = 3
    ) -> Tuple[str, List[SourceInfo]]:
        """질문에 대한 답변 생성"""
        try:
            if not self.openai_client:
                raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다")
            
            logger.info(f"질문 답변 생성 시작: {question[:50]}...")
            
            # 1. 관련 문서 검색 (Retrieval)
            relevant_chunks = await self._retrieve_relevant_chunks(
                question, 
                pdf_ids, 
                max_sources
            )
            
            if not relevant_chunks:
                logger.warning("관련 문서를 찾을 수 없습니다")
                return self._generate_fallback_answer(question), []
            
            # 2. 컨텍스트 구성
            context = self._build_context(relevant_chunks)
            
            # 3. 답변 생성 (Generation)
            answer = await self._generate_answer_with_context(question, context)
            
            # 4. 출처 정보 구성
            sources = self._extract_source_info(relevant_chunks)
            
            logger.info(f"질문 답변 생성 완료: {len(sources)}개 출처")
            
            return answer, sources
            
        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            return self._generate_error_answer(str(e)), []
    
    async def _retrieve_relevant_chunks(
        self, 
        question: str, 
        pdf_ids: Optional[List[str]], 
        max_sources: int
    ) -> List[Dict[str, Any]]:
        """질문과 관련된 텍스트 청크 검색"""
        try:
            # 벡터 검색으로 유사한 청크 찾기
            search_results = await self.vectorizer.search_similar(
                query=question,
                pdf_ids=pdf_ids,
                top_k=max_sources * 2,  # 더 많은 결과를 가져와서 필터링
                similarity_threshold=settings.SIMILARITY_THRESHOLD
            )
            
            # 결과 정렬 및 필터링
            filtered_results = []
            for result in search_results:
                # 중복 내용 제거
                if not self._is_duplicate_content(result, filtered_results):
                    filtered_results.append(result)
                
                if len(filtered_results) >= max_sources:
                    break
            
            logger.info(f"관련 청크 검색 완료: {len(filtered_results)}개")
            return filtered_results
            
        except Exception as e:
            logger.error(f"관련 청크 검색 실패: {e}")
            return []
    
    def _is_duplicate_content(
        self, 
        new_result: Dict[str, Any], 
        existing_results: List[Dict[str, Any]]
    ) -> bool:
        """중복 내용 확인"""
        new_content = new_result['content'].lower().strip()
        
        for existing in existing_results:
            existing_content = existing['content'].lower().strip()
            
            # 내용이 80% 이상 유사하면 중복으로 간주
            if self._calculate_similarity(new_content, existing_content) > 0.8:
                return True
        
        return False
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """간단한 텍스트 유사도 계산"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """검색된 청크들을 컨텍스트로 구성"""
        try:
            context_parts = []
            
            for i, chunk in enumerate(chunks):
                content = chunk['content']
                metadata = chunk['metadata']
                
                # 컨텍스트에 출처 정보 포함
                source_info = f"[출처 {i+1}: {metadata.get('pdf_metadata', {}).get('title', 'Unknown')} - 페이지 {metadata.get('page_number', 'Unknown')}]"
                
                context_parts.append(f"{source_info}\n{content}\n")
            
            context = "\n".join(context_parts)
            
            # 컨텍스트 길이 제한
            max_context_length = 4000  # 토큰 제한 고려
            if len(context) > max_context_length:
                context = context[:max_context_length] + "..."
            
            return context
            
        except Exception as e:
            logger.error(f"컨텍스트 구성 실패: {e}")
            return ""
    
    async def _generate_answer_with_context(self, question: str, context: str) -> str:
        """컨텍스트를 사용하여 답변 생성"""
        try:
            # 프롬프트 구성
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(question, context)
            
            # OpenAI API 호출
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.7,
                timeout=30
            )
            
            answer = response.choices[0].message.content.strip()
            return answer
            
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            raise
    
    def _build_system_prompt(self) -> str:
        """시스템 프롬프트 구성"""
        return """당신은 논문 PDF를 분석하는 전문 AI 어시스턴트입니다.

주요 역할:
1. 사용자의 질문에 대해 제공된 논문 내용을 바탕으로 정확하고 유용한 답변을 제공
2. 답변 시 반드시 출처를 명시하고, 인용된 내용을 정확하게 전달
3. 논문의 핵심 내용을 요약하고, 사용자가 이해하기 쉽게 설명
4. 기술적 용어나 개념을 명확하게 설명

답변 작성 규칙:
- 제공된 컨텍스트 내의 정보만을 사용하여 답변
- 추측이나 일반적인 지식은 사용하지 않음
- 출처 정보를 명확하게 표시
- 한국어로 답변 (사용자가 한국어로 질문한 경우)
- 간결하고 명확한 문장으로 작성
- 필요시 예시나 설명을 추가하여 이해를 돕기"""
    
    def _build_user_prompt(self, question: str, context: str) -> str:
        """사용자 프롬프트 구성"""
        return f"""질문: {question}

참고할 논문 내용:
{context}

위의 논문 내용을 바탕으로 질문에 답변해주세요. 답변 시 반드시 출처를 명시하고, 인용된 내용을 정확하게 전달해주세요."""
    
    def _extract_source_info(self, chunks: List[Dict[str, Any]]) -> List[SourceInfo]:
        """출처 정보 추출"""
        sources = []
        
        for chunk in chunks:
            metadata = chunk['metadata']
            pdf_metadata = metadata.get('pdf_metadata', {})
            
            source = SourceInfo(
                content=chunk['content'][:200] + "..." if len(chunk['content']) > 200 else chunk['content'],
                page_number=metadata.get('page_number', 0),
                pdf_filename=pdf_metadata.get('title', metadata.get('file_path', 'Unknown')),
                similarity_score=chunk.get('similarity_score', 0.0)
            )
            
            sources.append(source)
        
        return sources
    
    def _generate_fallback_answer(self, question: str) -> str:
        """관련 문서가 없을 때의 대체 답변"""
        return f"""죄송합니다. 질문 "{question}"에 대한 답변을 찾을 수 없습니다.

가능한 이유:
1. 업로드된 PDF에 관련 내용이 없음
2. PDF가 아직 벡터화되지 않음
3. 질문이 너무 구체적이거나 특수함

해결 방법:
1. 다른 PDF를 업로드해보세요
2. 질문을 더 일반적으로 바꿔보세요
3. PDF 벡터화 상태를 확인해보세요"""
    
    def _generate_error_answer(self, error_message: str) -> str:
        """오류 발생 시의 답변"""
        return f"""죄송합니다. 답변 생성 중 오류가 발생했습니다.

오류 내용: {error_message}

잠시 후 다시 시도해주시거나, 다른 질문을 해보세요."""
    
    async def generate_summary(
        self, 
        pdf_ids: List[str], 
        summary_type: str = "general"
    ) -> str:
        """PDF 문서 요약 생성"""
        try:
            if not self.openai_client:
                raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다")
            
            # 모든 PDF의 청크 가져오기
            all_chunks = []
            for pdf_id in pdf_ids:
                chunks = await self.vectorizer.get_document_chunks(pdf_id)
                all_chunks.extend(chunks)
            
            if not all_chunks:
                return "요약할 내용이 없습니다."
            
            # 요약용 컨텍스트 구성
            summary_context = self._build_summary_context(all_chunks)
            
            # 요약 프롬프트 구성
            summary_prompt = self._build_summary_prompt(summary_context, summary_type)
            
            # OpenAI API 호출
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 논문 요약 전문가입니다. 논문의 핵심 내용을 간결하고 명확하게 요약해주세요."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=800,
                temperature=0.5,
                timeout=30
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _build_summary_context(self, chunks: List[Dict[str, Any]]) -> str:
        """요약용 컨텍스트 구성"""
        try:
            # 청크를 페이지 순으로 정렬
            sorted_chunks = sorted(chunks, key=lambda x: x['metadata'].get('page_number', 0))
            
            context_parts = []
            for chunk in sorted_chunks:
                content = chunk['content']
                metadata = chunk['metadata']
                page_num = metadata.get('page_number', 'Unknown')
                
                context_parts.append(f"[페이지 {page_num}]\n{content}\n")
            
            context = "\n".join(context_parts)
            
            # 컨텍스트 길이 제한
            max_length = 6000
            if len(context) > max_length:
                context = context[:max_length] + "..."
            
            return context
            
        except Exception as e:
            logger.error(f"요약 컨텍스트 구성 실패: {e}")
            return ""
    
    def _build_summary_prompt(self, context: str, summary_type: str) -> str:
        """요약 프롬프트 구성"""
        type_descriptions = {
            "general": "전체 논문의 핵심 내용을 요약",
            "methodology": "연구 방법론과 실험 설계에 초점",
            "results": "주요 연구 결과와 발견사항에 초점",
            "conclusion": "결론과 향후 연구 방향에 초점"
        }
        
        description = type_descriptions.get(summary_type, "전체 논문의 핵심 내용을 요약")
        
        return f"""다음 논문 내용을 {description}해주세요.

논문 내용:
{context}

요약 시 다음 사항을 포함해주세요:
1. 연구의 주요 목적과 배경
2. 핵심 방법론
3. 주요 결과
4. 연구의 의의와 한계점

간결하고 명확하게 작성해주세요."""
    
    async def health_check(self) -> bool:
        """RAG 엔진 상태 확인"""
        try:
            # OpenAI 연결 확인
            if not self.openai_client:
                return False
            
            # 벡터라이저 상태 확인
            vectorizer_healthy = await self.vectorizer.health_check()
            
            return vectorizer_healthy
            
        except Exception as e:
            logger.error(f"RAG 엔진 상태 확인 실패: {e}")
            return False
