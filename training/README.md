# DIME — Model Training Guide

Complete training instructions for fine-tuning the Brain (Qwen2.5-VL-7B) and Coder (Qwen2.5-Coder-7B) models. Both DGX A100 and Windows RTX 4080 setups are documented — switching between them is a config change.

## Prerequisites

```bash
# Install LLaMA-Factory (works on both DGX and Windows/WSL)
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]"
```

## 1. Dataset Construction

Before training, build the dataset from your JEE PDFs:

```bash
python training/dataset_builder.py \
    --questions-dir data/questions \
    --solutions-dir data/solutions \
    --output-dir data/training \
    --split-ratio 0.8 0.1 0.1
```

This produces:
- `data/training/brain_train.json` — Brain training data (question → scene JSON)
- `data/training/brain_val.json` — Brain validation data
- `data/training/coder_train.json` — Coder training data (blueprint → Manim code)
- `data/training/coder_val.json` — Coder validation data

### Dataset Format

**Brain dataset** (each entry):
```json
{
  "messages": [
    {"role": "system", "content": "<Brain system prompt>"},
    {"role": "user", "content": "Solve this JEE question: <question text>"},
    {"role": "assistant", "content": "<scene JSON output>"}
  ],
  "images": ["path/to/question_image.png"]
}
```

**Coder dataset** (each entry):
```json
{
  "messages": [
    {"role": "system", "content": "<Coder system prompt>"},
    {"role": "user", "content": "<Director blueprint + timestamps>"},
    {"role": "assistant", "content": "<complete Manim Python code>"}
  ]
}
```

## 2. Training on DGX A100

### Brain Model (Qwen2.5-VL-7B)

```bash
# Request GPU allocation (single A100 is sufficient)
# From the DGX node:

CUDA_VISIBLE_DEVICES=7 llamafactory-cli train training/brain_config.yaml
```

**Config: `training/brain_config.yaml`**
- LoRA rank 32, targets all linear layers
- 3 epochs, batch size 4, gradient accumulation 4
- Learning rate 2e-4, bf16 precision
- Expected time: ~4 hours on A100

### Coder Model (Qwen2.5-Coder-7B)

```bash
CUDA_VISIBLE_DEVICES=7 llamafactory-cli train training/coder_config.yaml
```

**Config: `training/coder_config.yaml`**
- Same hyperparameters as Brain
- Training data: blueprint+timestamps → Manim code
- Expected time: ~3-4 hours on A100

### After Training — Deploy

```bash
# Merge LoRA adapter into base model
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen2.5-VL-7B-Instruct \
    --adapter_name_or_path checkpoints/brain_v1 \
    --export_dir models/brain_finetuned \
    --finetuning_type lora \
    --template qwen2_vl

# Serve with vLLM
python -m vllm.entrypoints.openai.api_server \
    --model models/brain_finetuned \
    --port 8001 \
    --max-model-len 8192
```

## 3. Training on Windows RTX 4080

The same configs work with these adjustments:

```bash
# Use AWQ quantized base model (fits in 16GB VRAM)
# Modify brain_config.yaml:
#   model_name_or_path: Qwen/Qwen2.5-VL-7B-Instruct-AWQ
#   quantization_bit: 4

# Reduce batch size to fit memory
#   per_device_train_batch_size: 1
#   gradient_accumulation_steps: 16

CUDA_VISIBLE_DEVICES=0 llamafactory-cli train training/brain_config.yaml
```

**Key differences from DGX:**

| Setting | DGX A100 (32GB) | RTX 4080 (16GB) |
|---------|-----------------|-----------------|
| Base model | Full precision (bf16) | AWQ 4-bit quantized |
| Batch size | 4 | 1 |
| Gradient accumulation | 4 | 16 |
| Training time | ~4 hours | ~8-12 hours |
| Max model len | 8192 | 4096 |
| Result quality | Identical (LoRA adapts same layers) |

### Switching Between DGX and RTX 4080

The LoRA adapters are **portable** between environments:
1. Train on DGX → download `checkpoints/` folder → use on RTX 4080
2. Train on RTX 4080 → upload to DGX → merge and serve at full precision

## 4. Evaluation

After training, evaluate on the held-out test set:

```bash
# Brain evaluation: does it produce valid scene JSON?
python -c "
from training.evaluate import evaluate_brain
evaluate_brain('models/brain_finetuned', 'data/training/brain_test.json')
"

# Coder evaluation: does the generated code render?
python -c "
from training.evaluate import evaluate_coder
evaluate_coder('models/coder_finetuned', 'data/training/coder_test.json')
"
```

**Target metrics:**
- Brain: >90% valid JSON schema, >85% correct visual_type
- Coder: >85% first-pass render success rate

## 5. Iterative Improvement

As the system runs in production:
1. Every scene needing retries → the final working code becomes training data
2. New error patterns → add to `error_patcher.py` known-fix library
3. New visual types you manually code → add to template library
4. **Re-train monthly** with accumulated data — models continuously improve
