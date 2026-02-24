import argparse
import json
from pathlib import Path
from collections import defaultdict
from typing import Optional, Dict, Iterable

def iter_json_object(path: Path) -> Optional[Dict]:
    # 각 파일은 [ { ... } ] 형태라고 가정
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return None

def write_pretty_json_array_stream(out_path: Path, items: Iterable[Dict], indent: int = 2) -> int:
    """
    JSON 배열 파일을 스트리밍으로 작성하면서도 사람이 보기 좋게 pretty-print 한다.
    메모리를 크게 쓰지 않음.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        for item in items:
            if item is None:
                continue
            if not first:
                f.write(",\n")
            f.write(json.dumps(item, ensure_ascii=False, indent=indent))
            first = False
            count += 1
        f.write("\n]\n")
    return count

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", required=True, help="e.g. data/train_simple or data/train")
    ap.add_argument("--out_dir", required=True, help="e.g. data/train_merged")
    ap.add_argument("--exclude_unknown", action="store_true")
    ap.add_argument("--indent", type=int, default=2, help="pretty json indent size")
    args = ap.parse_args()

    in_dir = Path(args.in_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    # CWE -> list of file paths
    buckets = defaultdict(list)
    for p in in_dir.rglob("*.json"):
        # 입력이 .../CWE-xxx/CVE-xxxx.json 구조라고 가정
        cwe = p.parent.name
        if args.exclude_unknown and "unknown" in cwe.lower():
            continue
        buckets[cwe].append(p)

    total_in = sum(len(v) for v in buckets.values())
    print(f"Found CWE folders: {len(buckets)}")
    print(f"Found input CVE json files (after filters): {total_in}")

    for cwe, paths in sorted(buckets.items()):
        paths = sorted(paths, key=lambda x: x.name)

        def items_gen():
            for p in paths:
                obj = iter_json_object(p)
                if obj is not None:
                    yield obj

        out_path = out_dir / f"{cwe}.json"
        wrote = write_pretty_json_array_stream(out_path, items_gen(), indent=args.indent)
        print(f"Wrote {out_path} (items={wrote}, from_files={len(paths)})")

if __name__ == "__main__":
    main()