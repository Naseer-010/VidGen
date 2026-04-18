"""
DIME — Phase 4: Known-Fix Error Patcher.

Applies regex-based patches for common Manim API errors
BEFORE any LLM retry — saves latency and cost.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KnownFix:
    """A known Manim API error and its fix."""

    name: str
    error_pattern: str  # regex to match in traceback
    code_find: str  # string to find in source code
    code_replace: str  # replacement string
    description: str


# ═════════════════════════════════════════════════════════════
# Known Error → Fix Library
# Grows over time as new patterns are discovered in production
# ═════════════════════════════════════════════════════════════

KNOWN_FIXES: list[KnownFix] = [
    KnownFix(
        name="ShowCreation_deprecated",
        error_pattern=r"ShowCreation|name 'ShowCreation' is not defined",
        code_find="ShowCreation",
        code_replace="Create",
        description="ShowCreation was renamed to Create in ManimCE 0.16+",
    ),
    KnownFix(
        name="FadeInFrom_deprecated",
        error_pattern=r"FadeInFrom|name 'FadeInFrom' is not defined",
        code_find="FadeInFrom",
        code_replace="FadeIn",
        description="FadeInFrom was deprecated; use FadeIn with shift parameter",
    ),
    KnownFix(
        name="GrowFromCenter_deprecated",
        error_pattern=r"GrowFromCenter|name 'GrowFromCenter' is not defined",
        code_find="GrowFromCenter",
        code_replace="GrowFromPoint",
        description="GrowFromCenter renamed to GrowFromPoint",
    ),
    KnownFix(
        name="DrawBorderThenFill_deprecated",
        error_pattern=r"DrawBorderThenFill|name 'DrawBorderThenFill' is not defined",
        code_find="DrawBorderThenFill",
        code_replace="Create",
        description="DrawBorderThenFill removed; use Create instead",
    ),
    KnownFix(
        name="missing_self_wait",
        error_pattern=r"animation.*shorter than|duration mismatch",
        code_find="",  # Special handling — append wait at end
        code_replace="",
        description="Auto-append self.wait() at end if render duration mismatch",
    ),
    KnownFix(
        name="latex_missing_dollar",
        error_pattern=r"LaTeX.*error|! Missing \$ inserted",
        code_find="",  # Special handling
        code_replace="",
        description="Common LaTeX syntax error — missing $ sign",
    ),
    KnownFix(
        name="unclosed_brace",
        error_pattern=r"Missing }|Unexpected end of input|unclosed.*brace",
        code_find="",  # Special handling
        code_replace="",
        description="Unclosed LaTeX braces",
    ),
    KnownFix(
        name="TexTemplate_not_found",
        error_pattern=r"TexTemplate|name 'TexTemplate' is not defined",
        code_find="TexTemplate",
        code_replace="Tex",
        description="TexTemplate API change",
    ),
    KnownFix(
        name="ThreeDScene_import",
        error_pattern=r"ThreeDScene|name 'ThreeDScene' is not defined",
        code_find="from manim import *",
        code_replace="from manim import *\nfrom manim.scene.three_d_scene import ThreeDScene",
        description="ThreeDScene needs explicit import in newer Manim",
    ),
    KnownFix(
        name="wrong_self_play",
        error_pattern=r"play.*takes|unexpected keyword argument",
        code_find="self.play(",
        code_replace="self.play(",
        description="self.play() argument errors",
    ),
]


def apply_known_fixes(
    source_code: str,
    traceback: str,
) -> tuple[str, list[str]]:
    """
    Apply known fixes to Manim source code based on traceback.

    Returns:
        (patched_code, list_of_applied_fixes)
    """
    applied = []
    patched = source_code

    for fix in KNOWN_FIXES:
        if not re.search(fix.error_pattern, traceback, re.IGNORECASE):
            continue

        # ── Special cases ────────────────────────────────────
        if fix.name == "missing_self_wait":
            patched = _fix_missing_wait(patched)
            applied.append(fix.name)
            continue

        if fix.name == "latex_missing_dollar":
            patched = _fix_latex_dollars(patched)
            applied.append(fix.name)
            continue

        if fix.name == "unclosed_brace":
            patched = _fix_unclosed_braces(patched)
            applied.append(fix.name)
            continue

        # ── Standard find-replace ────────────────────────────
        if fix.code_find and fix.code_find in patched:
            patched = patched.replace(fix.code_find, fix.code_replace)
            applied.append(fix.name)
            logger.info("Applied fix: %s — %s", fix.name, fix.description)

    if applied:
        logger.info("Patcher applied %d fixes: %s", len(applied), ", ".join(applied))
    else:
        logger.info("Patcher: no known fixes matched traceback")

    return patched, applied


def _fix_missing_wait(code: str) -> str:
    """Append self.wait(1) at the end of the construct method."""
    # Find the last line of construct()
    lines = code.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            # Get indentation of this line
            indent = len(lines[i]) - len(lines[i].lstrip())
            lines.insert(i + 1, " " * indent + "self.wait(1)")
            break
    return "\n".join(lines)


def _fix_latex_dollars(code: str) -> str:
    """Fix common LaTeX dollar sign issues in MathTex/Tex strings."""
    # Find MathTex(...) and Tex(...) calls and ensure proper $ usage
    # MathTex already wraps in $, so remove redundant $
    code = re.sub(
        r'MathTex\(r?"\$([^"]*)\$"\)',
        r'MathTex(r"\1")',
        code,
    )
    code = re.sub(
        r"MathTex\(r?'\$([^']*)\$'\)",
        r"MathTex(r'\1')",
        code,
    )
    return code


def _fix_unclosed_braces(code: str) -> str:
    """Try to fix unclosed braces in LaTeX strings."""

    # Find strings in MathTex/Tex calls
    def fix_braces(match):
        s = match.group(0)
        opens = s.count("{")
        closes = s.count("}")
        if opens > closes:
            s = s + "}" * (opens - closes)
        return s

    code = re.sub(r"(?:MathTex|Tex)\([^)]+\)", fix_braces, code)
    return code
