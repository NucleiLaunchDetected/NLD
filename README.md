## 📂 Project Structure

### `1. DTO (Data Transfer Objects)`
데이터의 형태를 정의하는 클래스들입니다.
- **`dto/rawdiffdto.py`**: Git에서 추출한 **날것의 Diff 정보** (변경 전/후 코드, 패치 내용, 파일 경로, 커밋 해시 등).
- **`dto/query_dto.py`**: 검색 엔진(RAG)에서 사용할 **정규화된 쿼리** (키워드 + 자연어 질문 + 필터링 정보).
- **`dto/vulnerability_knowledge_dto.py`**: LLM이 분석하여 추출한 **고도화된 취약점 지식** (원인, 해결책, 동작 원리 등 JSON 구조).

### `2. Pipelines (Extraction & Processing)`
실제 데이터를 처리하는 엔진들입니다.
- **`piplines/diff_extractor.py`**:
    - **역할**: Git 저장소에서 특정 커밋의 코드를 추출합니다.
    - **기능**: `code_before`, `code_after`, `patch` 추출 및 변경된 라인 파싱.
- **`piplines/query_generator.py`**:
    - **역할**: `RawDiffDTO`를 검색 가능한 `StructuredQueryDTO`로 변환합니다.
    - **기능**: 정규식으로 함수명 추출, LLM으로 검색 키워드 및 자연어 질문 생성.
- **`piplines/pipeline_extract.py`**:
    - **역할**: 취약점 분석 및 지식 추출의 핵심 파이프라인.
    - **기능**: **CoT(Chain-of-Thought)** 프롬프트를 사용하여 [목적 -> 기능 -> 분석 -> 지식] 순서로 심층 분석 수행.
- **`piplines/llm_client.py`**:
    - **역할**: LLM 모델(OpenAI, Ollama 등)과 통신하는 클라이언트.

---

## 🔄 Data Pipeline Flow

1.  **Git Input** (`DiffExtractor`)
    *   입력: Git Repo + Commit Hash
    *   출력: `RawDiffDTO` (원본 코드 + Diff)
2.  **Analysis & Extraction** (`KnowledgeExtractor`)
    *   입력: `RawDiffDTO`
    *   처리: LLM이 코드를 분석 (CoT 프롬프트)
    *   출력: `VulnerabilityKnowledgeDTO` (원인, 해결책, 분석 정보 JSON)
3.  **Normalisation** (`QueryGenerator`)
    *   입력: `RawDiffDTO`
    *   처리: 검색 용이성을 위해 데이터 정규화
    *   출력: `StructuredQueryDTO` (검색 쿼리용 메타데이터)
4.  **RAG Storage (Next Step)**
    *   입력: `VulnerabilityKnowledgeDTO` + `StructuredQueryDTO`
    *   저장: Vector DB (Hybrid Search)

---

## 🚀 Next Steps (RAG Construction)

이제 추출된 데이터를 저장하고 검색하는 **RAG 시스템**을 구축할 차례입니다.

1.  **Retriever 설계**: Hybrid Search (키워드 + 벡터) 구조 잡기.
2.  **Vector DB 연동**: ChromaDB, FAISS 등을 사용하여 데이터 저장.
3.  **Grav CMS Mapping**: 추출된 지식을 Grav CMS의 실제 코드 스코프와 매핑.