import subprocess
import re
from typing import Optional, Dict, List

class DiffExtractor:
    """
    Git 저장소에서 특정 커밋의 변경 사항(Diff)과 변경 전후 코드를 추출
    """
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> str:
        """Git 명령어 실행 헬퍼 함수"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git 명령어 실행 실패: {' '.join(args)}\n에러: {e.stderr}")
            raise e

    def get_file_content(self, commit_hash: str, file_path: str) -> str:
        """특정 커밋 시점의 파일 전체 내용을 반환합니다."""
        try:
            return self._run_git(["show", f"{commit_hash}:{file_path}"])
        except Exception:
            return ""

    def get_diff(self, commit_hash: str, file_path: str) -> str:
        """
        특정 커밋에서 해당 파일의 Diff(Patch)를 반환합니다.
        부모 커밋(commit_hash^)과 비교합니다.
        """
        return self._run_git(["diff", f"{commit_hash}^", commit_hash, "--", file_path])

    def parse_diff_for_modified_lines(self, diff_text: str) -> Dict[str, List[int]]:
        """
        Diff 텍스트를 파싱하여 추가/삭제된 라인 번호를 추출합니다.
        """
        added_lines = []
        deleted_lines = []
        
        current_old_line = 0
        current_new_line = 0
        
        for line in diff_text.splitlines():
            # Hunk 헤더 파싱 (예: @@ -10,5 +10,6 @@)
            if line.startswith("@@"):
                match = re.search(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
                if match:
                    current_old_line = int(match.group(1))
                    current_new_line = int(match.group(2))
            # 추가된 라인
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(current_new_line)
                current_new_line += 1
            # 삭제된 라인
            elif line.startswith("-") and not line.startswith("---"):
                deleted_lines.append(current_old_line)
                current_old_line += 1
            # 변경 없는 라인
            else:
                current_old_line += 1
                current_new_line += 1
                
        return {"added": added_lines, "deleted": deleted_lines}

    def get_changed_files(self, commit_hash: str) -> List[str]:
        """
        특정 커밋에서 변경된 파일 목록을 반환합니다.
        """
        output = self._run_git(["show", "--name-only", "--pretty=format:", commit_hash])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def extract_raw_diff(self, commit_hash: str, file_path: str) -> Dict:
        """
        RawDiffDTO 생성에 필요한 원본 데이터를 추출합니다.
        """
        try:
            # 1. 변경 전/후 코드 추출
            code_before = self.get_file_content(f"{commit_hash}^", file_path)
            code_after = self.get_file_content(commit_hash, file_path)
            
            # 2. Patch(Diff) 추출
            patch = self.get_diff(commit_hash, file_path)
            
            # 3. 변경된 라인 정보 파싱
            modified_lines = self.parse_diff_for_modified_lines(patch)
            
            return {
                "commit_hash": commit_hash,
                "file_path": file_path,
                "code_before_change": code_before,
                "code_after_change": code_after,
                "patch": patch,
                "function_modified_lines": modified_lines
            }
        except Exception as e:
            print(f"추출 실패 ({commit_hash}, {file_path}): {e}")
            return {}
