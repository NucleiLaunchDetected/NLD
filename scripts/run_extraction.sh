#!/bin/bash
# Knowledge Extraction Pipeline Runner

# 사용 예제
# ./scripts/run_extraction.sh CVE-2021-3904.json gpt-4o-mini

INPUT_FILE=${1:-"CVE-2021-3904.json"}
MODEL_NAME=${2:-"gpt-4o-mini"}
OUTPUT_FILE=$(echo $INPUT_FILE | sed 's/.json/_knowledge.json/')

echo "===================================="
echo "Knowledge Extraction Pipeline"
echo "===================================="
echo "Input:  data/train/$INPUT_FILE"
echo "Model:  $MODEL_NAME"
echo "Output: data/knowledge/$OUTPUT_FILE"
echo "===================================="

python3 src/pipelines/pipeline_extract.py \
    --input_file_name "$INPUT_FILE" \
    --output_file_name "$OUTPUT_FILE" \
    --model_name "$MODEL_NAME" \
    --model_settings "temperature=0.2;max_tokens=4096" \
    --thread_pool_size 3 \
    --retry_time 3 \
    --resume

echo ""
echo "✓ Complete!"
