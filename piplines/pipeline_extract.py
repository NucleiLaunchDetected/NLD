import json
from typing import List, Optional

from dto import RawDiffDTO, VulnerabilityKnowledgeDTO, VulnerabilityBehavior
from llm_client import LLMClient


def load_train_data(train_json_path: str) -> List[RawDiffDTO]:
    """train JSON 파일을 RawDiffDTO 리스트로 로드"""
    with open(train_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    out: List[RawDiffDTO] = []
    for item in data:
        try:
            out.append(RawDiffDTO(**item))
        except Exception as e:
            print(f"[SKIP] RawDiffDTO parse failed: {e}")
    return out


def build_prompt(raw: RawDiffDTO) -> str:
    """LLM에 줄 단일 프롬프트(목표: JSON 출력)"""
    return f"""
This is a code snippet with a vulnerability {raw.cve_id}:
'''
{raw.code_before_change}
'''

The vulnerability is described as follows:
{raw.cve_description}

The correct way to fix it is by adding/deleting:
'''
{raw.function_modified_lines}
'''

Fixed code (after patch):
'''
{raw.code_after_change}
'''

Now output JSON in the following exact schema (no extra keys):
{{
  "vulnerability_behavior": {{
    "vulnerability_cause_description": "...",
    "trigger_condition": "...",
    "specific_code_behavior_causing_vulnerability": "..."
  }},
  "solution": "...",
  "purpose": "...",
  "function": "...",
  "analysis": "..."
}}

Rules:
- solution is plain text (no nested dict/list).
- Omit specific variable/resource names to keep it generalized.
""".strip()


def safe_json_loads(text: str) -> Optional[dict]:
    """LLM이 JSON 앞뒤에 잡문 붙여도 {}만 잘라 파싱 시도"""
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def infer_metadata(raw: RawDiffDTO) -> dict:
    """optional 메타데이터 자동 추정(없어도 됨)"""
    desc = (raw.cve_description or "").lower()
    before = raw.code_before_change or ""

    vuln_type = "xss" if "xss" in desc else None

    language = None
    if "<?php" in before:
        language = "php"
    elif "{%" in before or "{{" in before:
        language = "twig"

    tags = []
    if vuln_type:
        tags.append(vuln_type)
    for c in (raw.cwe or []):
        if isinstance(c, str):
            tags.append(c.lower())

    return {"vuln_type": vuln_type, "language": language, "tags": tags or None}


def llm_response_to_dto(raw: RawDiffDTO, llm_text: str) -> Optional[VulnerabilityKnowledgeDTO]:
    """LLM JSON 문자열 → VulnerabilityKnowledgeDTO 객체"""
    data = safe_json_loads(llm_text)
    if not data:
        print(f"[SKIP] JSON parse failed: {raw.cve_id}")
        return None

    try:
        vb = data["vulnerability_behavior"]
        behavior = VulnerabilityBehavior(
            vulnerability_cause_description=vb["vulnerability_cause_description"],
            trigger_condition=vb["trigger_condition"],
            specific_code_behavior_causing_vulnerability=vb["specific_code_behavior_causing_vulnerability"],
        )

        meta = infer_metadata(raw)

        return VulnerabilityKnowledgeDTO(
            CVE_id=raw.cve_id,
            vulnerability_behavior=behavior,
            solution=data["solution"],
            purpose=data["purpose"],
            function=data["function"],
            analysis=data["analysis"],
            code_before_change=raw.code_before_change,
            code_after_change=raw.code_after_change,
            modified_lines=raw.function_modified_lines,

            # flat copy
            vulnerability_cause_description=behavior.vulnerability_cause_description,
            trigger_condition=behavior.trigger_condition,
            specific_code_behavior_causing_vulnerability=behavior.specific_code_behavior_causing_vulnerability,

            # optional
            vuln_type=meta["vuln_type"],
            language=meta["language"],
            tags=meta["tags"],
        )
    except Exception as e:
        print(f"[SKIP] DTO mapping failed for {raw.cve_id}: {e}")
        return None


def extract_knowledge_objects(
    train_json_path: str,
    client: LLMClient,
    limit: Optional[int] = None,
) -> List[VulnerabilityKnowledgeDTO]:
    """
    train.json → RawDiffDTO → LLM → VulnerabilityKnowledgeDTO 객체 리스트
    (여기까지가 '파일로 JSON 저장 전' 단계)
    """
    raws = load_train_data(train_json_path)
    if limit:
        raws = raws[:limit]

    out: List[VulnerabilityKnowledgeDTO] = []

    for raw in raws:
        prompt = build_prompt(raw)

        try:
            llm_text = client.generate(prompt)
        except Exception as e:
            print(f"[LLM ERROR] {raw.cve_id}: {e}")
            continue

        dto = llm_response_to_dto(raw, llm_text)
        if dto:
            out.append(dto)

    return out


if __name__ == "__main__":
    client = LLMClient(model_name="dummy")
    objs = extract_knowledge_objects("benchmark/train/train.json", client, limit=3)
    print(f"created {len(objs)} knowledge DTO objects")
