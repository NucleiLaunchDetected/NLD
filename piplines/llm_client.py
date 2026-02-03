import os
import json
from typing import Optional

class LLMClient:
    """
    LLM API 클라이언트 래퍼.
    OpenAI, Anthropic, Ollama 등 다양한 백엔드를 지원하도록 확장 가능.
    현재는 Mock/Dummy 모드로 동작하거나 환경 변수가 있으면 OpenAI를 사용하도록 구성 예시.
    """
    def __init__(self, provider: str = "openai", model_name: str = "gpt-4o"):
        self.provider = provider
        self.model_name = model_name
        self.api_key = os.getenv("OPENAI_API_KEY")

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        프롬프트를 받아 LLM 응답 텍스트를 반환.
        """
        # TODO: 실제 API 호출 구현
        # 지금은 테스트를 위해 간단한 Mock 응답 또는 에러 처리
        if self.provider == "dummy":
            return self._dummy_response(prompt)
        
        # if self.provider == "openai" and self.api_key:
        #     return self._call_openai(prompt, system_prompt)
            
        print(f"[LLMClient] Warning: No valid provider configured. Returning mock.")
        return self._dummy_response(prompt)

    def _dummy_response(self, prompt: str) -> str:
        """테스트용 더미 응답"""
        return json.dumps({
            "summary": "This is a dummy response based on the prompt.",
            "keywords": ["vulnerability", "patch", "security"],
            "analysis": "Mock analysis content."
        })

    def _call_openai(self, prompt: str, system_prompt: str) -> str:
        # pip install openai 필요
        # 실제 구현 시 주석 해제 및 패키지 설치
        # from openai import OpenAI
        # client = OpenAI(api_key=self.api_key)
        # response = client.chat.completions.create(...)
        # return response.choices[0].message.content
        raise NotImplementedError("OpenAI integration not yet enabled.")