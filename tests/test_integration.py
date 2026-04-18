"""
DIME — Integration Tests.

Tests for:
- Schema validation
- Hash computation
- Error patcher
- Config loading
"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestModels:
    """Test Pydantic data models."""

    def test_brain_output_valid(self):
        from src.models import BrainOutput, Scene, VisualType

        data = {
            "question_type": "physics",
            "topic": "Kinematics",
            "difficulty": "medium",
            "scenes": [
                {
                    "scene_id": "scene_01",
                    "duration_estimate_sec": 8.0,
                    "narration": "Let us analyze this projectile problem step by step.",
                    "visual_type": "projectile",
                    "visual_params": {"u": 20, "theta": 45, "g": 10},
                }
            ],
            "final_answer": "R = 40 m",
        }
        output = BrainOutput.model_validate(data)
        assert output.question_type == "physics"
        assert len(output.scenes) == 1
        assert output.scenes[0].visual_type == VisualType.PROJECTILE

    def test_brain_output_invalid_visual_type(self):
        from src.models import BrainOutput

        data = {
            "question_type": "physics",
            "topic": "Test",
            "difficulty": "easy",
            "scenes": [
                {
                    "scene_id": "scene_01",
                    "duration_estimate_sec": 5.0,
                    "narration": "Some narration for the test scene.",
                    "visual_type": "invalid_type",
                    "visual_params": {},
                }
            ],
            "final_answer": "42",
        }
        with pytest.raises(Exception):
            BrainOutput.model_validate(data)

    def test_job_defaults(self):
        from src.models import Job, JobStatus

        job = Job()
        assert job.status == JobStatus.QUEUED
        assert len(job.job_id) == 36  # UUID format

    def test_generate_request_validation(self):
        from src.models import GenerateRequest

        req = GenerateRequest(question_text="What is F=ma?")
        assert req.has_input()

        req_empty = GenerateRequest()
        assert not req_empty.has_input()


class TestIngestion:
    """Test hash computation."""

    def test_text_hash_deterministic(self):
        from src.pipeline.ingestion import compute_text_hash

        h1 = compute_text_hash("What is the velocity?")
        h2 = compute_text_hash("What is the velocity?")
        assert h1 == h2

    def test_text_hash_normalizes(self):
        from src.pipeline.ingestion import compute_text_hash

        h1 = compute_text_hash("What is the velocity?")
        h2 = compute_text_hash("  WHAT  IS  THE  VELOCITY?  ")
        assert h1 == h2

    def test_different_questions_different_hash(self):
        from src.pipeline.ingestion import compute_text_hash

        h1 = compute_text_hash("What is velocity?")
        h2 = compute_text_hash("What is acceleration?")
        assert h1 != h2


class TestErrorPatcher:
    """Test known-fix error patcher."""

    def test_show_creation_fix(self):
        from src.pipeline.error_patcher import apply_known_fixes

        code = "self.play(ShowCreation(circle))"
        traceback = "name 'ShowCreation' is not defined"
        patched, fixes = apply_known_fixes(code, traceback)
        assert "Create" in patched
        assert "ShowCreation_deprecated" in fixes

    def test_fade_in_from_fix(self):
        from src.pipeline.error_patcher import apply_known_fixes

        code = "self.play(FadeInFrom(text, UP))"
        traceback = "name 'FadeInFrom' is not defined"
        patched, fixes = apply_known_fixes(code, traceback)
        assert "FadeIn" in patched
        assert "FadeInFrom_deprecated" in fixes

    def test_no_match_returns_unchanged(self):
        from src.pipeline.error_patcher import apply_known_fixes

        code = "self.play(Write(text))"
        traceback = "some random error"
        patched, fixes = apply_known_fixes(code, traceback)
        assert patched == code
        assert len(fixes) == 0


class TestValidator:
    """Test Wolfram Alpha validator utilities."""

    def test_extract_numbers(self):
        from src.pipeline.validator import _extract_numbers

        nums = _extract_numbers("v = 17.3 m/s at 30 degrees")
        assert 17.3 in nums
        assert 30.0 in nums

    def test_compare_answers_exact(self):
        from src.pipeline.validator import _compare_answers

        assert _compare_answers("42", "42") is True

    def test_compare_answers_tolerance(self):
        from src.pipeline.validator import _compare_answers

        assert _compare_answers("17.3", "17.31") is True
        assert _compare_answers("17.3", "20.0") is False
