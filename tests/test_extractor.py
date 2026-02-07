
import sys
import os

# Add project root to path
sys.path.append(r"c:\Users\jyj20\Desktop\KW\BlackCat\project\NLD")

from piplines.diff_extractor import DiffExtractor
from dto.rawdiffdto import RawDiffDTO

def test_extraction():
    # Use the current repo path
    repo_path = r"c:\Users\jyj20\Desktop\KW\BlackCat\project\NLD"
    extractor = DiffExtractor(repo_path)
    
    # Get the latest commit hash to test
    try:
        import subprocess
        output = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True)
        commit_hash = output.stdout.strip()
        print(f"Testing with commit: {commit_hash}")
        
        # Test getting changed files
        files = extractor.get_changed_files(commit_hash)
        print(f"Changed files: {files}")
        
        if files:
            target_file = files[0]
            print(f"Extracting raw diff for: {target_file}")
            
            # Test extract_raw_diff
            data = extractor.extract_raw_diff(commit_hash, target_file)
            
            # Validate with DTO
            dto = RawDiffDTO(**data, cve_id="TEST-CVE-001")
            print("\nSuccessfully created RawDiffDTO:")
            print(f"- Code Before Length: {len(dto.code_before_change)}")
            print(f"- Code After Length: {len(dto.code_after_change)}")
            print(f"- Patch Length: {len(dto.patch)}")
            print(f"- Modified Lines: {dto.function_modified_lines}")
        else:
            print("No files changed in this commit (merge commit?).")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
