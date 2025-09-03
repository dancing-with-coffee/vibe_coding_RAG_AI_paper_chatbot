from openai import OpenAI
from typing import List, Dict
from .vector_store import VectorStore
from .config import settings

class RAGEngine:
    def __init__(self):
        self.vector_store = VectorStore()
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def generate_response(self, query: str) -> Dict:
        """쿼리에 대한 RAG 응답을 생성합니다."""
        # 1. 관련 문서 검색
        relevant_docs = self.vector_store.search_similar(query, n_results=5)
        
        if not relevant_docs:
            return {
                "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                "sources": []
            }
        
        # 2. 컨텍스트 구성
        context = self._build_context(relevant_docs)
        
        # 3. 프롬프트 생성
        prompt = self._create_prompt(query, context)
        
        # 4. OpenAI API 호출
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "당신은 AI 연구 논문 전문가입니다. 주어진 논문 내용을 바탕으로 정확하고 도움이 되는 답변을 제공해주세요. 답변은 한국어로 해주세요."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # 5. 소스 정보 추출
            sources = self._extract_sources(relevant_docs)
            
            return {
                "answer": answer,
                "sources": sources
            }
            
        except Exception as e:
            return {
                "answer": f"답변 생성 중 오류가 발생했습니다: {str(e)}",
                "sources": []
            }
    
    def _build_context(self, docs: List[Dict]) -> str:
        """문서들로부터 컨텍스트를 구성합니다."""
        context = "다음은 관련 논문 내용입니다:\n\n"
        
        for i, doc in enumerate(docs, 1):
            filename = doc['metadata']['filename']
            text = doc['text'][:500]  # 길이 제한
            context += f"[논문 {i}: {filename}]\n{text}\n\n"
        
        return context
    
    def _create_prompt(self, query: str, context: str) -> str:
        """프롬프트를 생성합니다."""
        return f"""
컨텍스트:
{context}

질문: {query}

위의 논문 내용을 바탕으로 질문에 대해 정확하고 자세한 답변을 해주세요. 
답변할 때는 어떤 논문에서 나온 정보인지 언급해주세요.
만약 제공된 논문 내용으로는 충분한 답변을 할 수 없다면, 그렇다고 명확히 말해주세요.
"""
    
    def _extract_sources(self, docs: List[Dict]) -> List[Dict]:
        """소스 정보를 추출합니다."""
        sources = []
        seen_files = set()
        
        for doc in docs:
            filename = doc['metadata']['filename']
            if filename not in seen_files:
                sources.append({
                    'filename': filename,
                    'relevance_score': 1.0 - doc['distance']  # distance를 relevance로 변환
                })
                seen_files.add(filename)
        
        return sources[:3]  # 상위 3개만 반환
