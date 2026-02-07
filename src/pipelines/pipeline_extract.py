"""
Knowledge Extraction Pipeline
RawDiffDTO JSON → LLM 분석 → VulnerabilityKnowledgeDTO JSON

Usage:
    python src/piplines/pipeline_extract.py \
        --input_file_name CVE-2021-3904.json \
        --output_file_name CVE-2021-3904_knowledge.json \
        --model_name gpt-4o-mini \
        --model_settings "temperature=0.2;max_tokens=4096" \
        --thread_pool_size 5 \
        --retry_time 3 \
        --resume
"""
import json
import os
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils import llm_client
from tqdm import tqdm
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
import time
from functools import wraps

MODEL_CLIENT = None
output_lock = threading.Lock()
file_lock = threading.Lock()


def retry_on_failure(max_retries: int = 5, delay: float = 1.0):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1: 
                        print(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                        time.sleep(delay)
                    continue
            raise last_exception 
        return wrapper
    return decorator


def parse_args():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description="Extract vulnerability knowledge using LLM")
    parser.add_argument("--input_file_name", type=str, required=True, 
                       help="Input JSON file name (in data/train/)")
    parser.add_argument("--output_file_name", type=str, required=True,
                       help="Output JSON file name (in data/knowledge/)")
    parser.add_argument("--model_name", type=str, required=True,
                       help="LLM model name (e.g., gpt-4o-mini, gpt-4o, gpt-4-turbo)")
    parser.add_argument(
        '--model_settings',
        type=str,
        default=None,
        help='Model settings in key-value format: "temperature=0.2;max_tokens=1024"'
    )
    parser.add_argument(
        '--thread_pool_size',
        type=int,
        default=5,
        help="Number of parallel threads for processing"
    )
    parser.add_argument(
        '--retry_time',
        type=int,
        default=5,
        help="Number of retries on API failure"
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoint if exists'
    )
    args = parser.parse_args()
    args.model_settings = llm_client.parse_kv_string_to_dict(args.model_settings)
    return args


def generate_extract_prompt(cve_id, cve_description, modified_lines, code_before, code_after):
    """
    단계별 프롬프트 생성
    
    Returns:
        tuple: (purpose_prompt, function_prompt, analysis_prompt, knowledge_extraction_prompt)
    """
    prefix_str = f"""This is a code snippet with a vulnerability {cve_id}:
'''
{code_before}
'''
The vulnerability is described as follows:
{cve_description}
"""

    # Step 1: Extract purpose
    purpose_prompt = f"""{prefix_str}
What is the purpose of the function in the above code snippet? \
Please summarize the answer in one sentence with following format: Function purpose: \"\"
"""

    # Step 2: Extract function summary
    function_prompt = f"""{prefix_str}
Please summarize the functions of the above code snippet in the list format without other \
explanation: \"The functions of the code snippet are: 1. 2. 3.\"
"""

    # Step 3: Extract analysis
    analysis_prompt = f"""{prefix_str}
The correct way to fix it is by adding/deleting
'''
{json.dumps(modified_lines, indent=2)}
'''
"""

    if modified_lines.get("added"):
        analysis_prompt += f"""The code after modification is as follows:\n'''\n{code_after}\n'''\n"""

    analysis_prompt += """Why is the above modification necessary?"""

    # Step 4: Knowledge extraction
    knowledge_extraction_prompt = """
I want you to act as a vulnerability detection expert and organize vulnerability knowledge based on the above \
vulnerability repair information. Please summarize the generalizable specific behavior of the code that \
leads to the vulnerability and the specific solution to fix it. Format your findings in JSON.

Here are some examples to guide you on the level of detail expected in your extraction:

Example 1:
{
    "vulnerability_behavior": {
        "vulnerability_cause_description": "Lack of proper handling for asynchronous events during device removal process.",
        "trigger_condition": "A physically proximate attacker unplugs a device while the removal function is executing, leading to a race condition and use-after-free vulnerability.",
        "specific_code_behavior_causing_vulnerability": "The code does not cancel pending work associated with a specific functionality before proceeding with further cleanup during device removal. This can result in a use-after-free scenario if the device is unplugged at a critical moment."
    }, 
    "solution": "To mitigate the vulnerability, it is necessary to cancel any pending work related to the specific functionality before proceeding with further cleanup during device removal. This ensures that the code handles asynchronous events properly and prevents the use-after-free vulnerability."
}

IMPORTANT:
- In the 'solution' field, describe the solution in natural language format.
- Do NOT nest dictionaries or arrays within the 'solution' field.
- Do NOT nest within other fields either.
- Your answer should be exactly the same format as the example provided.
- Omit specific resource names to ensure the knowledge remains generalized (e.g., use mutex_lock instead of mutex_lock(&dmxdev->mutex)).
- Return ONLY valid JSON, no markdown formatting like ```json.
"""

    return purpose_prompt, function_prompt, analysis_prompt, knowledge_extraction_prompt


def parse_vulnerability_knowledge(llm_output: str) -> Dict[str, Any]:
    """
    LLM 출력에서 vulnerability_behavior JSON 추출
    """
    try:
        # JSON 블록 찾기
        if "```json" in llm_output:
            llm_output = llm_output.split("```json")[1].split("```")[0]
        elif "```" in llm_output:
            llm_output = llm_output.split("```")[1].split("```")[0]
        
        # vulnerability_behavior 찾기
        if "\"vulnerability_behavior\"" in llm_output:
            llm_output = llm_output.split("\"vulnerability_behavior\"")[1]
            llm_output = "{\"vulnerability_behavior\"" + llm_output
        
        # 정리
        if "\n```" in llm_output:
            llm_output = llm_output.split("\n```")[0]
        
        return json.loads(llm_output)
    except Exception as e:
        print(f"Error parsing LLM output: {e}")
        print(f"Output: {llm_output[:200]}...")
        raise


def extract_knowledge(args, item: Dict[str, Any], output_data: List[Dict[str, Any]]) -> None:
    """
    단일 CVE 항목에 대해 지식 추출
    """
    try:
        global MODEL_CLIENT
        
        def generate_with_retry(prompt_dict, settings):
            """재시도 로직이 포함된 생성 함수"""
            last_exception = None
            for attempt in range(args.retry_time):
                try:
                    return MODEL_CLIENT.generate_text(prompt_dict, settings)
                except Exception as e:
                    last_exception = e
                    if attempt < args.retry_time - 1:
                        print(f"[{item['cve_id']}] Attempt {attempt + 1}/{args.retry_time} failed: {str(e)}")
                        time.sleep(1.0)
                    continue
            raise last_exception

        # 프롬프트 생성
        purpose_prompt, function_prompt, analysis_prompt, knowledge_extraction_prompt = generate_extract_prompt(
            item["cve_id"], 
            item["cve_description"], 
            item["function_modified_lines"], 
            item["code_before_change"], 
            item["code_after_change"]
        )

        # Step 1: Extract Purpose
        purpose_prompt_dict = llm_client.generate_simple_prompt(purpose_prompt)
        purpose_output = generate_with_retry(purpose_prompt_dict, args.model_settings)

        # Step 2: Extract Function Summary
        function_prompt_dict = llm_client.generate_simple_prompt(function_prompt)
        function_output = generate_with_retry(function_prompt_dict, args.model_settings)

        # Step 3: Extract Analysis
        messages = llm_client.generate_simple_prompt(analysis_prompt)
        analysis_output = generate_with_retry(messages, args.model_settings)

        # Step 4: Extract Vulnerability Knowledge
        messages.append({"role": "assistant", "content": analysis_output})
        messages.append({"role": "user", "content": knowledge_extraction_prompt})
        knowledge_extraction_output = generate_with_retry(messages, args.model_settings)

        # Parse LLM output
        output_dict = parse_vulnerability_knowledge(knowledge_extraction_output)
        
        # Add metadata
        output_dict["analysis"] = analysis_output
        output_dict["purpose"] = llm_client.extract_LLM_response_by_prefix(
            purpose_output, "Function purpose:"
        )
        output_dict["function"] = llm_client.extract_LLM_response_by_prefix(
            function_output, "The functions of the code snippet are:"
        )
        
        # Add original data
        output_dict["CVE_id"] = item["cve_id"]
        output_dict["id"] = item["id"]
        output_dict["code_before_change"] = item["code_before_change"]
        output_dict["code_after_change"] = item["code_after_change"]
        output_dict["modified_lines"] = item["function_modified_lines"]

        # Extract solution if nested
        if "solution" in output_dict.get("vulnerability_behavior", {}):
            output_dict["solution"] = output_dict["vulnerability_behavior"]["solution"]
        
        # Flatten vulnerability_behavior fields
        vb = output_dict.get("vulnerability_behavior", {})
        output_dict["vulnerability_cause_description"] = vb.get("vulnerability_cause_description", "")
        output_dict["trigger_condition"] = vb.get("trigger_condition", "")
        output_dict["specific_code_behavior_causing_vulnerability"] = vb.get("specific_code_behavior_causing_vulnerability", "")

        # Thread-safe output
        with output_lock:
            output_data.append(output_dict)
            with file_lock:
                output_path = Path("data/knowledge") / args.output_file_name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False)
        
        print(f"✓ Processed {item['cve_id']}")
        
    except Exception as e:
        print(f"✗ Error processing {item['cve_id']}: {str(e)}")
        return


def process_item(args, item: Dict[str, Any], output_data: List[Dict[str, Any]], resume_set: set):
    """개별 아이템 처리"""
    if item["id"] not in resume_set:
        extract_knowledge(args, item, output_data)
    else:
        print(f"⊙ Skipping {item['cve_id']} (already processed)")


def extract_knowledge_pipeline(args):
    """메인 파이프라인"""
    global MODEL_CLIENT
    
    # LLM 클라이언트 초기화
    try:
        MODEL_CLIENT = llm_client.get_llm_client(args.model_name)
        print(f"Initialized LLM Client: {MODEL_CLIENT.model_name}")
    except Exception as e:
        print(f"Failed to initialize LLM client: {e}")
        sys.exit(1)
    
    # 입력 데이터 로드
    input_path = Path("data/train") / args.input_file_name
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} items from {input_path}")
    
    # Resume 처리
    output_data = []
    resume_set = set()
    
    if args.resume:
        output_path = Path("data/knowledge") / args.output_file_name
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                output_data = json.load(f)
                resume_set = set([item["id"] for item in output_data])
            print(f"Resuming: Found {len(resume_set)} already processed items")
    
    # 병렬 처리
    print(f"Processing with {args.thread_pool_size} threads...")
    with ThreadPoolExecutor(max_workers=args.thread_pool_size) as executor:
        list(tqdm(
            executor.map(
                lambda item: process_item(args, item, output_data, resume_set),
                data
            ),
            total=len(data),
            desc="Extracting Knowledge"
        ))
    
    print(f"\n✓ Complete! Processed {len(output_data)} items")
    print(f"  Output: data/knowledge/{args.output_file_name}")


if __name__ == "__main__":
    args = parse_args()
    extract_knowledge_pipeline(args)
