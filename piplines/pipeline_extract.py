import json
from typing import List, Optional, Dict

from dto.rawdiffdto import RawDiffDTO
from dto.vulnerability_knowledge_dto import VulnerabilityKnowledgeDTO, VulnerabilityBehavior
from piplines.llm_client import LLMClient


def build_cot_prompt(raw: RawDiffDTO) -> str:
    """
    Chain-of-Thought(CoT) 스타일의 프롬프트를 생성
    목적, 기능, 분석을 단계별로 추론하도록 하고, 마지막에 JSON 형태로 지식을 추출
    """
    
    modified_lines_str = json.dumps(raw.function_modified_lines, indent=2, ensure_ascii=False)
    
    prompt = f"""
You are a vulnerability analysis expert. Given the following code snippet and vulnerability patch information, please analyze deeply and extract structured knowledge.

### Context
CVE ID: {raw.cve_id}
Description: {raw.cve_description}

### Code (Before Change)
'''
{raw.code_before_change}
'''

### Patch Information
The correct fix involves the following line changes:
{modified_lines_str}

Code after modification:
'''
{raw.code_after_change}
'''

### Instructions
Please mimic a Chain-of-Thought (CoT) process to extract the required information step-by-step.

Step 1. **Purpose Analysis**: Briefly describe the purpose of the target function in one sentence.
Step 2. **Function Summary**: List the main functionalities of the code snippet.
Step 3. **Vulnerability Analysis**: Explain why the modification was necessary, identifying the root cause and the fix logic.
Step 4. **Knowledge Extraction**: Based on the analysis, generalize the vulnerability behavior and solution.

### Output Format
Finally, output the result in the following JSON format ONLY. Ensure the content is generalized (omit specific variable/resource names where appropriate).

{{
  "purpose": "Step 1 result here...",
  "function": "Step 2 result here...",
  "analysis": "Step 3 result here...",
  "vulnerability_behavior": {{
    "vulnerability_cause_description": "General description of the cause...",
    "trigger_condition": "How an attacker triggers it...",
    "specific_code_behavior_causing_vulnerability": "What the code does wrong..."
  }},
  "solution": "Generalized solution in plain text..."
}}

Rules:
- Output **valid JSON** only.
- No markdown formatting (like ```json).
- Ensure the 'solution' is a single string, not a nested object.
"""
    return prompt.strip()


def safe_json_loads(text: str) -> Optional[dict]:
    """
    LLM 응답에서 JSON 부분을 안전하게 파싱합니다.
    """
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # JSON 블록 찾기 시도
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
            
    return None

class KnowledgeExtractor:
    """
    Git Diff 정보(RawDiffDTO)를 입력받아 LLM을 통해 분석하고 
    지식 데이터(VulnerabilityKnowledgeDTO)로 변환하는 클래스입니다.
    """
    def __init__(self, llm_client: LLMClient):
        self.client = llm_client

    def process_single(self, raw: RawDiffDTO) -> Optional[VulnerabilityKnowledgeDTO]:
        print(f"Processing {raw.cve_id}...")

        # CoT 프롬프트 생성
        prompt = build_cot_prompt(raw)
        
        # LLM 호출
        response_text = self.client.generate(prompt)
        
        # 응답 파싱
        data = safe_json_loads(response_text)
        if not data:
            print(f"[FAIL] JSON parse failed for {raw.cve_id}")
            # 디버깅을 위해 응답 일부 출력
            print(f"Raw Response: {response_text[:100]}...") 
            return None

        try:
            # 안전하게 파싱된 데이터를 DTO로 변환
            vb_data = data.get("vulnerability_behavior", {})
            behavior = VulnerabilityBehavior(
                vulnerability_cause_description=vb_data.get('vulnerability_cause_description', ''),
                trigger_condition=vb_data.get('trigger_condition', ''),
                specific_code_behavior_causing_vulnerability=vb_data.get('specific_code_behavior_causing_vulnerability', '')
            )
            
            return VulnerabilityKnowledgeDTO(
                CVE_id=raw.cve_id,
                vulnerability_behavior=behavior,
                solution=data.get("solution", ""),
                purpose=data.get("purpose", ""),
                function=data.get("function", ""),
                analysis=data.get("analysis", ""),
                code_before_change=raw.code_before_change,
                code_after_change=raw.code_after_change,
                modified_lines=raw.function_modified_lines,
                
                # Flat fields Mapping
                vulnerability_cause_description=behavior.vulnerability_cause_description,
                trigger_condition=behavior.trigger_condition,
                specific_code_behavior_causing_vulnerability=behavior.specific_code_behavior_causing_vulnerability
            )
        except Exception as e:
            print(f"[ERROR] DTO mapping failed for {raw.cve_id}: {e}")
            return None

def run_extraction(train_json_path: str, client: LLMClient):
    """
    파일 경로에서 학습 데이터를 로드하여 추출을 수행하는 헬퍼 함수
    """
    with open(train_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extractor = KnowledgeExtractor(client)
    results = []
    
    for item in data:
        try:
            raw = RawDiffDTO(**item)
            dto = extractor.process_single(raw)
            if dto:
                results.append(dto)
        except Exception as e:
            print(f"[SKIP] Item processing error: {e}")
            
    return results
