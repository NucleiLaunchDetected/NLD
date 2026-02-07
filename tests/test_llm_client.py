"""
LLM Client 테스트 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import llm_client

def test_dummy_client():
    """Dummy 클라이언트 테스트"""
    print("=" * 60)
    print("Testing Dummy Client")
    print("=" * 60)
    
    client = llm_client.get_llm_client("dummy")
    messages = llm_client.generate_simple_prompt("Test vulnerability analysis")
    response = client.generate_text(messages)
    
    print(f"Model: {client.model_name}")
    print(f"Response: {response[:200]}...")
    print("[OK] Dummy client works!\n")


def test_real_client(model_name: str):
    """실제 LLM 클라이언트 테스트"""
    print("=" * 60)
    print(f"Testing {model_name}")
    print("=" * 60)
    
    try:
        client = llm_client.get_llm_client(model_name)
        messages = llm_client.generate_simple_prompt("Say 'Hello from AI!'")
        
        settings = {"temperature": 0.2, "max_tokens": 50}
        response = client.generate_text(messages, settings)
        
        print(f"Model: {client.model_name}")
        print(f"Response: {response}")
        print(f"[OK] {model_name} works!\n")
        
    except ValueError as e:
        print(f"[ERROR] API key not found: {e}\n")
    except ImportError as e:
        print(f"[ERROR] Package not installed: {e}\n")
    except Exception as e:
        print(f"[ERROR] {e}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test LLM clients")
    parser.add_argument("--model", type=str, default="dummy",
                       help="Model to test (dummy, gpt-4o-mini, deepseek-chat, claude-3-5-sonnet)")
    args = parser.parse_args()
    
    if args.model == "dummy":
        test_dummy_client()
    else:
        test_real_client(args.model)
