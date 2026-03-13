import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# ENV
# =========================
load_dotenv()

client = OpenAI()

# =========================
# Paths
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = BASE_DIR / "data" / "diff" / "diff_retriever.json"

RESULT_PATH = BASE_DIR / "data" / "evaluation" / "evaluation_results.json"
SUMMARY_PATH = BASE_DIR / "data" / "evaluation" / "evaluation_summary.json"
FAILED_PATH = BASE_DIR / "data" / "evaluation" / "evaluation_failed.json"

# =========================
# Config
# =========================
MODEL = "gpt-4o-mini"

MAX_ITEMS = None  # 예: 50

METRICS = [
    "hallucination",
    "relevance",
    "helpfulness",
    "context_relevance",
    "retrieval_usefulness"
]

# =========================
# Prompt
# =========================
EVAL_PROMPT = """
You are a security researcher evaluating AI generated explanations of source code.

Evaluate the explanation quality.

Return ONLY JSON.

Scoring criteria (1-5):

hallucination:
1 = mostly incorrect
3 = partially correct
5 = fully grounded in code

relevance:
1 = unrelated to code
3 = partially relevant
5 = highly relevant

helpfulness:
1 = not helpful
3 = somewhat helpful
5 = very helpful

context_relevance:
1 = incorrect context
3 = partially correct
5 = correct context

retrieval_usefulness:
1 = not useful for retrieval
3 = somewhat useful
5 = useful for retrieval

INPUT:

Function name:
{function}

Code:
{code}

Purpose:
{purpose}

Summary:
{summary}

OUTPUT JSON FORMAT:

{{
"hallucination": 1-5,
"relevance": 1-5,
"helpfulness": 1-5,
"context_relevance": 1-5,
"retrieval_usefulness": 1-5,
"reasoning": "short explanation"
}}
"""


# =========================
# Evaluate single item
# =========================
def evaluate_item(item):

    code = item.get("full_code", "")[:1500]

    prompt = EVAL_PROMPT.format(
        function=item.get("function", ""),
        code=code,
        purpose=item.get("purpose", ""),
        summary=item.get("function_summary", "")
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    raw = response.choices[0].message.content

    try:
        parsed = json.loads(raw)
    except Exception:
        return None, raw

    result = {}

    for m in METRICS:
        try:
            score = int(parsed.get(m))
            if 1 <= score <= 5:
                result[m] = score
            else:
                result[m] = None
        except:
            result[m] = None

    result["reasoning"] = parsed.get("reasoning", "")

    if any(v is None for v in result.values() if isinstance(v, int) or v is None):
        return None, raw

    return result, raw


# =========================
# Save json helper
# =========================
def save_json(path, data):

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# =========================
# Main
# =========================
def main():

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if MAX_ITEMS:
        data = data[:MAX_ITEMS]

    results = []
    failed = []

    print(f"Total items: {len(data)}")

    for i, item in enumerate(data):

        print(f"Evaluating {i+1}/{len(data)}")

        evaluation, raw = evaluate_item(item)

        if evaluation is None:

            failed.append({
                "item": item,
                "raw_response": raw
            })

            continue

        item_result = dict(item)
        item_result["evaluation"] = evaluation

        results.append(item_result)

    # =========================
    # compute averages
    # =========================
    summary = {
        "total_input_items": len(data),
        "success_count": len(results),
        "failed_count": len(failed),
        "averages": {}
    }

    if results:

        for m in METRICS:

            vals = [r["evaluation"][m] for r in results]

            summary["averages"][m] = round(sum(vals) / len(vals), 3)

    else:

        for m in METRICS:
            summary["averages"][m] = None

    # =========================
    # save
    # =========================
    save_json(RESULT_PATH, results)
    save_json(FAILED_PATH, failed)
    save_json(SUMMARY_PATH, summary)

    print("\nEvaluation summary")

    print(json.dumps(summary, indent=2))

    print("\nSaved:")
    print(RESULT_PATH)
    print(FAILED_PATH)
    print(SUMMARY_PATH)


# =========================
# run
# =========================
if __name__ == "__main__":
    main()