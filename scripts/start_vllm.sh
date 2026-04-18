#!/usr/bin/env bash
# ============================================================
# DIME — vLLM Server Launcher
#
# Starts vLLM inference servers for Brain and Coder models.
# Usage:
#   bash scripts/start_vllm.sh                    # Default: local backend
#   bash scripts/start_vllm.sh --backend dgx      # DGX backend
#   bash scripts/start_vllm.sh --backend local     # Local RTX 4080
#   bash scripts/start_vllm.sh --quantized         # Use AWQ quantization (RTX 4080)
# ============================================================

set -euo pipefail

BACKEND="${2:-local}"
QUANTIZED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            BACKEND="$2"
            shift 2
            ;;
        --quantized)
            QUANTIZED=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo "🚀 Starting DIME vLLM servers (backend=$BACKEND, quantized=$QUANTIZED)"

# ── Model names ──────────────────────────────────────────────
BRAIN_MODEL="Qwen/Qwen2.5-VL-7B-Instruct"
CODER_MODEL="Qwen/Qwen2.5-Coder-7B-Instruct"

if [ "$QUANTIZED" = true ]; then
    BRAIN_MODEL="Qwen/Qwen2.5-VL-7B-Instruct-AWQ"
    CODER_MODEL="Qwen/Qwen2.5-Coder-7B-Instruct-AWQ"
    echo "📦 Using AWQ quantized models"
fi

# ── Determine GPU allocation ────────────────────────────────
if [ "$BACKEND" = "dgx" ]; then
    BRAIN_GPU="0"
    CODER_GPU="1"
    BRAIN_PORT=8001
    CODER_PORT=8002
    MAX_MODEL_LEN=8192
    echo "🖥️  DGX mode: GPU $BRAIN_GPU (Brain), GPU $CODER_GPU (Coder)"
else
    BRAIN_GPU="0"
    CODER_GPU="0"
    BRAIN_PORT=8001
    CODER_PORT=8002
    MAX_MODEL_LEN=4096
    echo "🖥️  Local mode: Single GPU $BRAIN_GPU (both models)"
fi

# ── Start Brain model server ────────────────────────────────
echo "▶ Starting Brain model on port $BRAIN_PORT..."
CUDA_VISIBLE_DEVICES=$BRAIN_GPU python -m vllm.entrypoints.openai.api_server \
    --model "$BRAIN_MODEL" \
    --served-model-name "$BRAIN_MODEL" \
    --port $BRAIN_PORT \
    --max-model-len $MAX_MODEL_LEN \
    --enable-prefix-caching \
    --trust-remote-code \
    --dtype auto \
    --gpu-memory-utilization 0.45 \
    --host 0.0.0.0 \
    2>&1 | tee logs/brain_vllm.log &

BRAIN_PID=$!
echo "   Brain PID: $BRAIN_PID"

# Wait a bit for Brain to load before starting Coder
if [ "$BACKEND" = "local" ]; then
    echo "⏳ Waiting 60s for Brain model to load (sharing GPU)..."
    sleep 60
fi

# ── Start Coder model server ────────────────────────────────
echo "▶ Starting Coder model on port $CODER_PORT..."
CUDA_VISIBLE_DEVICES=$CODER_GPU python -m vllm.entrypoints.openai.api_server \
    --model "$CODER_MODEL" \
    --served-model-name "$CODER_MODEL" \
    --port $CODER_PORT \
    --max-model-len $MAX_MODEL_LEN \
    --trust-remote-code \
    --dtype auto \
    --gpu-memory-utilization 0.45 \
    --host 0.0.0.0 \
    2>&1 | tee logs/coder_vllm.log &

CODER_PID=$!
echo "   Coder PID: $CODER_PID"

# ── Save PIDs for management ────────────────────────────────
mkdir -p logs
echo "$BRAIN_PID" > logs/brain_vllm.pid
echo "$CODER_PID" > logs/coder_vllm.pid

echo ""
echo "✅ vLLM servers starting..."
echo "   Brain: http://0.0.0.0:$BRAIN_PORT/v1  (PID $BRAIN_PID)"
echo "   Coder: http://0.0.0.0:$CODER_PORT/v1  (PID $CODER_PID)"
echo ""
echo "   Check health: curl http://localhost:$BRAIN_PORT/health"
echo "   View logs:    tail -f logs/brain_vllm.log"
echo "   Stop servers: kill \$(cat logs/brain_vllm.pid) \$(cat logs/coder_vllm.pid)"

wait
