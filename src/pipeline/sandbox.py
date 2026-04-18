"""
DIME — Phase 4: Docker Sandbox Execution.

Runs LLM-generated Manim code inside a resource-limited Docker container.
    - 4GB memory limit, 2 CPU cores
    - No network access
    - Read-only filesystem (except /output)
    - 90-second timeout
    - Container destroyed after each scene
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from src.config import settings

logger = logging.getLogger(__name__)

# ── Docker client (lazy) ─────────────────────────────────────
_docker_client: Optional[docker.DockerClient] = None


def _get_docker() -> docker.DockerClient:
    """Get or create Docker client."""
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def ensure_sandbox_image() -> bool:
    """Build the sandbox Docker image if it doesn't exist."""
    client = _get_docker()
    try:
        client.images.get(settings.docker_image_name)
        logger.info("Sandbox image '%s' exists", settings.docker_image_name)
        return True
    except ImageNotFound:
        logger.info("Building sandbox image '%s'...", settings.docker_image_name)
        try:
            dockerfile_path = Path(__file__).parent.parent.parent / "docker"
            client.images.build(
                path=str(dockerfile_path),
                dockerfile="Dockerfile.manim",
                tag=settings.docker_image_name,
                rm=True,
            )
            logger.info("✅ Sandbox image built successfully")
            return True
        except Exception as e:
            logger.error("Failed to build sandbox image: %s", e)
            return False


async def execute_in_sandbox(
    scene_code: str,
    scene_name: str,
    output_dir: str,
) -> tuple[bool, str, Optional[str]]:
    """
    Execute Manim code in a sandboxed Docker container.

    Args:
        scene_code: Complete Manim Python scene code
        scene_name: Name of the Scene class to render
        output_dir: Host directory for output files

    Returns:
        (success, output_path_or_traceback, stderr)
    """
    client = _get_docker()

    # Write scene code to a temp file
    os.makedirs(output_dir, exist_ok=True)
    scene_file = os.path.join(output_dir, f"{scene_name}.py")
    with open(scene_file, "w") as f:
        f.write(scene_code)

    container = None
    try:
        # Run in Docker container
        container = client.containers.run(
            image=settings.docker_image_name,
            command=[
                "-qh",
                "--format",
                "mp4",
                f"/workspace/{scene_name}.py",
                scene_name,
                "-o",
                f"/output/{scene_name}.mp4",
            ],
            volumes={
                scene_file: {"bind": f"/workspace/{scene_name}.py", "mode": "ro"},
                output_dir: {"bind": "/output", "mode": "rw"},
            },
            mem_limit=settings.docker_memory_limit,
            cpuset_cpus=f"0-{settings.docker_cpu_limit - 1}",
            network_mode="none",  # No network access
            remove=False,  # Keep for log inspection
            detach=True,
            environment={"DISPLAY": ""},  # No display needed
        )

        # Wait for completion with timeout
        result = container.wait(timeout=settings.manim_timeout_seconds)
        exit_code = result.get("StatusCode", -1)

        # Get logs
        stdout = container.logs(stdout=True, stderr=False).decode(
            "utf-8", errors="replace"
        )
        stderr = container.logs(stdout=False, stderr=True).decode(
            "utf-8", errors="replace"
        )

        # Check output
        output_path = os.path.join(output_dir, f"{scene_name}.mp4")

        if exit_code == 0 and os.path.exists(output_path):
            logger.info("✅ Sandbox render SUCCESS: %s", scene_name)
            return True, output_path, None
        else:
            error = stderr or stdout or f"Exit code: {exit_code}"
            logger.warning("❌ Sandbox render FAILED: %s → %s", scene_name, error[:200])
            return False, error, stderr

    except docker.errors.ContainerError as e:
        error = str(e)
        logger.warning("Container error for %s: %s", scene_name, error[:200])
        return False, error, str(e.stderr) if e.stderr else None

    except Exception as e:
        logger.error("Sandbox execution error for %s: %s", scene_name, e)
        return False, str(e), None

    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass


async def execute_locally(
    scene_code: str,
    scene_name: str,
    output_dir: str,
) -> tuple[bool, str, Optional[str]]:
    """
    Fallback: execute Manim locally without Docker.
    Use this if Docker is unavailable.
    """
    import asyncio
    import subprocess

    os.makedirs(output_dir, exist_ok=True)
    scene_file = os.path.join(output_dir, f"{scene_name}.py")
    with open(scene_file, "w") as f:
        f.write(scene_code)

    cmd = [
        "manim",
        "render",
        "-q" + settings.manim_quality,
        "--format",
        "mp4",
        scene_file,
        scene_name,
        "-o",
        os.path.join(output_dir, f"{scene_name}.mp4"),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=output_dir,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.manim_timeout_seconds,
        )

        output_path = os.path.join(output_dir, f"{scene_name}.mp4")

        # Also check media directory where Manim actually writes
        media_path = os.path.join(
            output_dir,
            "media",
            "videos",
            f"{scene_name}",
            "1080p60",
            f"{scene_name}.mp4",
        )

        actual_path = (
            output_path
            if os.path.exists(output_path)
            else (media_path if os.path.exists(media_path) else None)
        )

        if proc.returncode == 0 and actual_path:
            logger.info("✅ Local render SUCCESS: %s", scene_name)
            return True, actual_path, None
        else:
            error = stderr.decode("utf-8", errors="replace")
            logger.warning("❌ Local render FAILED: %s", error[:200])
            return False, error, error

    except asyncio.TimeoutError:
        logger.error(
            "Render timeout for %s (%ds)", scene_name, settings.manim_timeout_seconds
        )
        return False, f"Render timeout after {settings.manim_timeout_seconds}s", None
    except Exception as e:
        return False, str(e), None
