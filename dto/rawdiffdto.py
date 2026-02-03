from pydantic import BaseModel


class RawDiffDTO(BaseModel):
    """Train 데이터 - 원본 취약점 정보"""
    cve_id: str
    code_before_change: str
    code_after_change: str
    patch: str
    function_modified_lines: dict  # {"added": [...], "deleted": [...]}
    file_path: str = ""
    commit_hash: str = ""
    cwe: list[str] = []
    cve_description: str = ""
    id: int = 0
