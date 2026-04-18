"""
DIME — Phase 1: Brain (Multimodal Solver & Scene Scriptwriter).

Uses Qwen2.5-VL-7B via vLLM to:
1. Understand the JEE question (text or image)
2. Solve the mathematics
3. Write pedagogical narration
4. Structure into discrete visual scenes with strict JSON schema
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.backend import get_brain_client
from src.config import settings
from src.models import BrainOutput, VisualType

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════
# System Prompt — trains the Brain to produce scene JSON
# ═════════════════════════════════════════════════════════════

BRAIN_SYSTEM_PROMPT = """You are an expert JEE (Joint Entrance Examination) teacher and visual explainer.

Given a JEE-level question (Physics, Chemistry, or Mathematics), you must:
1. Solve the problem step-by-step with correct mathematics
2. Write clear, pedagogical narration as if explaining to a student
3. Structure the explanation into visual scenes for animation

OUTPUT FORMAT: You MUST respond with ONLY a valid JSON object (no markdown, no extra text).

The JSON schema:
{
  "question_type": "physics" | "chemistry" | "math",
  "topic": "<specific topic, e.g., 'Kinematics - Projectile Motion'>",
  "difficulty": "easy" | "medium" | "hard",
  "scenes": [
    {
      "scene_id": "scene_01",
      "duration_estimate_sec": <float 3-30>,
      "narration": "<Teacher-style narration for this scene>",
      "visual_type": "<one of the allowed types>",
      "visual_params": { <type-specific parameters> },
      "requires_codegen": false
    }
  ],
  "final_answer": "<numerical or symbolic answer>"
}

ALLOWED visual_type values (you MUST use exactly one of these):
- "equation_transform": Equation morphing (use for algebraic manipulation steps)
  params: {"from_expr": "...", "to_expr": "...", "intermediate_steps": [...]}

- "axes_plot": Graph on coordinate axes
  params: {"x_label": "...", "y_label": "...", "functions": [{"expr": "...", "color": "..."}], "x_range": [min, max], "y_range": [min, max]}

- "free_body": Force vectors on an object
  params: {"forces": [{"name": "F", "magnitude": 10, "angle": 45, "color": "YELLOW"}], "object_shape": "circle"|"rectangle"}

- "projectile": Parabolic trajectory
  params: {"u": <initial velocity>, "theta": <launch angle degrees>, "g": <gravity>, "show_components": true|false}

- "circuit": Electrical circuit
  params: {"components": [{"type": "resistor"|"capacitor"|"battery", "value": "...", "label": "..."}], "connections": [...]}

- "ray_diagram": Optics ray tracing
  params: {"element": "convex_lens"|"concave_lens"|"convex_mirror"|"concave_mirror", "focal_length": <float>, "object_distance": <float>}

- "reaction_mechanism": Chemical reaction visualization
  params: {"reactants": [...], "products": [...], "mechanism_steps": [...]}

- "orbital_diagram": Atomic orbital filling
  params: {"element": "...", "electrons": <int>, "show_hybridization": true|false}

- "number_line": Points/intervals on a number line
  params: {"points": [{"value": <float>, "label": "..."}], "intervals": [{"start": <float>, "end": <float>, "type": "open"|"closed"}], "range": [min, max]}

- "geometry_construction": Coordinate geometry shapes
  params: {"shapes": [{"type": "circle"|"line"|"parabola"|"ellipse", "equation": "...", "color": "..."}], "points": [{"x": <float>, "y": <float>, "label": "..."}]}

- "integration_area": Shaded area under/between curves
  params: {"functions": [{"expr": "..."}], "x_range": [a, b], "shade_between": true|false}

- "text_reveal": Step-by-step text appearing
  params: {"steps": ["Step 1: ...", "Step 2: ..."], "highlight_color": "YELLOW"}

RULES:
1. Each scene MUST have narration text that a teacher would actually say
2. Keep scenes to 5-15 seconds estimated duration
3. Use 3-6 scenes per question typically
4. Narration should be conversational — "Let's think about this..." not "The answer is..."
5. visual_params MUST contain all required parameters for the chosen visual_type
6. Set requires_codegen=true ONLY if the visual cannot be expressed by the standard params above
"""


async def run_brain(
    question_text: Optional[str] = None,
    question_image_base64: Optional[str] = None,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> BrainOutput:
    """
    Run the Brain model to solve a JEE question and produce scene JSON.

    Args:
        question_text: Plain text question
        question_image_base64: Base64-encoded image of the question
        temperature: Sampling temperature (lower = more deterministic)
        max_retries: Number of retries on parse failure

    Returns:
        BrainOutput with structured scene data
    """
    client = get_brain_client()

    # ── Build messages ───────────────────────────────────────
    messages = [{"role": "system", "content": BRAIN_SYSTEM_PROMPT}]

    user_content = []
    if question_image_base64:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{question_image_base64}"},
            }
        )
    if question_text:
        user_content.append(
            {
                "type": "text",
                "text": f"Solve this JEE question and produce the scene JSON:\n\n{question_text}",
            }
        )
    else:
        user_content.append(
            {
                "type": "text",
                "text": "Solve this JEE question from the image and produce the scene JSON.",
            }
        )

    messages.append({"role": "user", "content": user_content})

    # ── Call vLLM with retries ───────────────────────────────
    last_error = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=settings.brain_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )

            raw_output = response.choices[0].message.content.strip()
            logger.info(
                "Brain raw output (attempt %d): %s", attempt + 1, raw_output[:200]
            )

            # Parse and validate
            data = json.loads(raw_output)
            brain_output = BrainOutput.model_validate(data)

            logger.info(
                "Brain output: %s | %s | %d scenes | answer=%s",
                brain_output.question_type,
                brain_output.topic,
                len(brain_output.scenes),
                brain_output.final_answer,
            )
            return brain_output

        except json.JSONDecodeError as e:
            last_error = f"JSON parse error: {e}"
            logger.warning("Brain attempt %d: %s", attempt + 1, last_error)
            # Retry with explicit instruction
            messages.append(
                {
                    "role": "assistant",
                    "content": raw_output if "raw_output" in dir() else "",
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": "Your response was not valid JSON. Please respond with ONLY a valid JSON object, no markdown fences or extra text.",
                }
            )

        except Exception as e:
            last_error = str(e)
            logger.warning("Brain attempt %d failed: %s", attempt + 1, last_error)

    raise RuntimeError(f"Brain failed after {max_retries} attempts: {last_error}")
