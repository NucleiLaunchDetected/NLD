class LLMClient:
    """
    generate()를 환경(OpenAI/Ollama/vLLM)에 맞도록 변경
    반환값은 JSON 문자열
    """
    def __init__(self, model_name: str = "dummy"):
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        raise NotImplementedError("LLM 호출 로직을 구현해야 해.")