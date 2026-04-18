"""
DIME — Pydantic Data Models & Schemas.

Defines all data contracts between pipeline phases:
Scene JSON, Brain output, Director blueprint, Job state, API schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ═════════════════════════════════════════════════════════════
# Visual Type Enum — constrains Brain output to known types
# ═════════════════════════════════════════════════════════════


class VisualType(str, Enum):
    EQUATION_TRANSFORM = "equation_transform"
    AXES_PLOT = "axes_plot"
    FREE_BODY = "free_body"
    PROJECTILE = "projectile"
    CIRCUIT = "circuit"
    RAY_DIAGRAM = "ray_diagram"
    REACTION_MECHANISM = "reaction_mechanism"
    ORBITAL_DIAGRAM = "orbital_diagram"
    NUMBER_LINE = "number_line"
    GEOMETRY_CONSTRUCTION = "geometry_construction"
    INTEGRATION_AREA = "integration_area"
    TEXT_REVEAL = "text_reveal"


# ═════════════════════════════════════════════════════════════
# Scene — Single animation segment
# ═════════════════════════════════════════════════════════════


class Scene(BaseModel):
    """A single scene in the explanation video."""

    scene_id: str = Field(..., description="Unique ID like 'scene_01'")
    duration_estimate_sec: float = Field(..., ge=1.0, le=60.0)
    narration: str = Field(..., min_length=10, description="Teacher narration text")
    visual_type: VisualType = Field(..., description="One of 12 animation types")
    visual_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific parameters (e.g., u, theta, g for projectile)",
    )
    requires_codegen: bool = Field(
        False, description="True if template cannot handle this scene"
    )


# ═════════════════════════════════════════════════════════════
# Brain Output — Full solver response
# ═════════════════════════════════════════════════════════════


class BrainOutput(BaseModel):
    """Structured output from the Brain (Qwen2.5-VL-7B)."""

    question_type: str = Field(..., description="physics / chemistry / math")
    topic: str = Field(..., description="e.g., 'Kinematics - Projectile Motion'")
    difficulty: str = Field(..., description="easy / medium / hard")
    scenes: list[Scene] = Field(..., min_length=1, max_length=12)
    final_answer: str = Field(..., description="Numerical/symbolic final answer")


# ═════════════════════════════════════════════════════════════
# Director Blueprint — Layout coordinates
# ═════════════════════════════════════════════════════════════


class ObjectPlacement(BaseModel):
    """Manim coordinate + styling for a single visual element."""

    object_id: str
    position: str = Field(..., description="e.g., 'UP*2 + LEFT*1.5'")
    color: str = Field(default="WHITE")
    scale: float = Field(default=1.0, ge=0.1, le=5.0)


class DirectorBlueprint(BaseModel):
    """Director's coordinate layout for a single scene."""

    scene_id: str
    placements: list[ObjectPlacement] = Field(default_factory=list)
    camera_frame_width: float = Field(default=14.0)
    background_color: str = Field(default="#1e1e2e")


# ═════════════════════════════════════════════════════════════
# TTS Result — Audio + timestamps
# ═════════════════════════════════════════════════════════════


class WordTimestamp(BaseModel):
    """Word-level timing from TTS."""

    word: str
    start: float
    end: float


class TTSResult(BaseModel):
    """TTS output for a single scene."""

    scene_id: str
    audio_path: str
    duration_sec: float
    word_timestamps: list[WordTimestamp] = Field(default_factory=list)


# ═════════════════════════════════════════════════════════════
# Job State — Pipeline tracking
# ═════════════════════════════════════════════════════════════


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    BRAIN_COMPLETE = "brain_complete"
    TTS_COMPLETE = "tts_complete"
    RENDERING = "rendering"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """Tracks a single video generation job."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    question_text: Optional[str] = None
    question_hash: Optional[str] = None
    image_path: Optional[str] = None
    brain_output: Optional[BrainOutput] = None
    tts_results: list[TTSResult] = Field(default_factory=list)
    director_blueprints: list[DirectorBlueprint] = Field(default_factory=list)
    scene_video_paths: list[str] = Field(default_factory=list)
    final_video_path: Optional[str] = None
    video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0


# ═════════════════════════════════════════════════════════════
# API Schemas
# ═════════════════════════════════════════════════════════════


class GenerateRequest(BaseModel):
    """Request to generate a video."""

    question_text: Optional[str] = Field(None, description="Text question")
    question_image_base64: Optional[str] = Field(
        None, description="Base64-encoded image"
    )

    def has_input(self) -> bool:
        return bool(self.question_text) or bool(self.question_image_base64)


class GenerateResponse(BaseModel):
    """Response after queuing a generation job."""

    job_id: str
    status: JobStatus
    message: str
    poll_url: str
    video_url: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response for job status polling."""

    job_id: str
    status: JobStatus
    progress: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None


# ═════════════════════════════════════════════════════════════
# Pipeline State (for LangGraph)
# ═════════════════════════════════════════════════════════════


class PipelineState(BaseModel):
    """State object passed through the LangGraph pipeline."""

    job: Job
    brain_output: Optional[BrainOutput] = None
    tts_results: list[TTSResult] = Field(default_factory=list)
    director_blueprints: list[DirectorBlueprint] = Field(default_factory=list)
    scene_codes: dict[str, str] = Field(
        default_factory=dict, description="scene_id → Manim Python code"
    )
    scene_videos: dict[str, str] = Field(
        default_factory=dict, description="scene_id → rendered .mp4 path"
    )
    scene_errors: dict[str, str] = Field(
        default_factory=dict, description="scene_id → error traceback"
    )
    retry_counts: dict[str, int] = Field(
        default_factory=dict, description="scene_id → number of retries"
    )
    final_video_path: Optional[str] = None
    is_valid: bool = True
    validation_message: Optional[str] = None
