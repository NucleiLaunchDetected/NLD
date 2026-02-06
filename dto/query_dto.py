from pydantic import BaseModel
from typing import List, Optional

class StructuredQueryDTO(BaseModel):
    """
    Diff 정보를 바탕으로 검색(Retriever)에 사용할 정규화된 쿼리 구조.
    ElasticSearch/VectorDB 등에서 Hybrid Search를 수행하기 위한 메타데이터와 벡터용 텍스트를 포함.
    """
    # 1. Structured Filters (Exact Match / Filter)
    target_functions: List[str] = []   # 변경된 함수 이름 목록
    related_files: List[str] = []      # 변경된 파일 경로/이름
    file_extensions: List[str] = []    # .c, .py, .php 등
    
    # 2. Keywords (BM25 / Keyword Search)
    keywords: List[str] = []           # 코드 내 중요 키워드 (e.g., "memcpy", "buffer_size")
    
    # 3. Semantic Query (Vector Search)
    natural_language_queries: List[str] = [] # "buffer overflow fix in memcpy", "XSS patch in login"
    
    # 4. Meta Info
    commit_hash: Optional[str] = None
    project_name: Optional[str] = None
