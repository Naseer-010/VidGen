"""
DIME — Manim Documentation Ingestion Script.

Scrapes Manim Community docs, chunks by class/method,
embeds with BGE-M3, and stores in ChromaDB.

Usage:
    python -m src.rag.ingest_docs
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx

from src.rag.store import add_documents

logger = logging.getLogger(__name__)

# Key Manim documentation pages to ingest
MANIM_DOC_URLS = [
    "https://docs.manim.community/en/stable/reference/manim.animation.creation.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.transform.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.fading.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.text.tex_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.arc.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.line.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.graph.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.coordinate_systems.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.scene.html",
]

# Hand-curated Manim API reference chunks (more reliable than scraping)
MANIM_API_CHUNKS = [
    {
        "id": "animation_create",
        "text": """Manim Animation: Create
Create(mobject) - Draws a VMobject by gradually revealing its stroke.
Replaces the deprecated ShowCreation.
Usage: self.play(Create(circle))
Works with: Lines, Arcs, Circles, VMobjects with stroke.""",
    },
    {
        "id": "animation_write",
        "text": """Manim Animation: Write
Write(mobject) - Animates the writing of a text or LaTeX mobject.
Usage: self.play(Write(text))
Works with: Tex, MathTex, Text, VGroup of text objects.""",
    },
    {
        "id": "animation_fadein",
        "text": """Manim Animation: FadeIn / FadeOut
FadeIn(mobject, shift=UP) - Fades in a mobject, optionally with directional shift.
FadeOut(mobject) - Fades out a mobject.
Note: FadeInFrom is DEPRECATED. Use FadeIn(mob, shift=direction) instead.
Usage: self.play(FadeIn(title, shift=DOWN))""",
    },
    {
        "id": "animation_transform",
        "text": """Manim Animation: Transform / TransformMatchingTex
Transform(source, target) - Morphs source into target (source reference changes).
ReplacementTransform(source, target) - Morphs and replaces source with target.
TransformMatchingTex(eq1, eq2) - Transforms matching LaTeX parts between equations.
Usage: self.play(TransformMatchingTex(eq1, eq2))""",
    },
    {
        "id": "mobject_mathtex",
        "text": """Manim Mobject: MathTex / Tex
MathTex(r"\\frac{a}{b}") - Create math LaTeX. Already in math mode, NO $ needed.
Tex(r"Hello World") - Create text LaTeX.
Common methods:
  .scale(factor) - Scale the tex
  .set_color(COLOR) - Set color
  .move_to(position) - Position on screen
  .next_to(other, direction) - Position relative to another mobject
  .to_edge(direction) - Move to screen edge""",
    },
    {
        "id": "mobject_axes",
        "text": """Manim Mobject: Axes / NumberPlane
Axes(x_range=[min, max, step], y_range=[min, max, step], x_length=10, y_length=6)
Methods:
  .plot(func, color=BLUE) - Plot a function
  .get_graph_label(graph, label=MathTex(...)) - Add label to graph
  .get_area(graph, x_range=[a,b]) - Get shaded area under graph
  .c2p(x, y) - Convert coordinates to point
  .get_vertical_line(point) - Vertical dashed line""",
    },
    {
        "id": "mobject_arrow",
        "text": """Manim Mobject: Arrow / Line / Dot
Arrow(start, end, color=WHITE, buff=0.25) - Arrow between two points.
Line(start, end, color=WHITE) - Line segment.
DashedLine(start, end) - Dashed line.
Dot(point, color=WHITE, radius=DEFAULT_DOT_RADIUS) - Dot at a point.
DoubleArrow(start, end) - Arrow with tips on both ends.""",
    },
    {
        "id": "mobject_shapes",
        "text": """Manim Mobject: Shapes
Circle(radius=1, color=WHITE) - Circle.
Square(side_length=2) - Square.
Rectangle(width=4, height=2) - Rectangle.
Ellipse(width=4, height=2) - Ellipse.
Arc(radius=1, angle=PI/2) - Arc.
Polygon(*vertices) - Polygon from vertex list.
Triangle() - Equilateral triangle.
Common: .set_fill(color, opacity=0.5), .set_stroke(color, width=2)""",
    },
    {
        "id": "mobject_vgroup",
        "text": """Manim Mobject: VGroup
VGroup(*mobjects) - Group of visual mobjects.
Methods:
  .arrange(direction, buff=0.5) - Arrange children in a direction
  .arrange_in_grid(rows, cols) - Grid layout
  .scale_to_fit_height(h) - Scale to fit height
  .shift(direction) - Move group
  .next_to(other, direction) - Position relative""",
    },
    {
        "id": "scene_methods",
        "text": """Manim Scene Methods
self.play(*animations, run_time=1) - Play one or more animations.
self.wait(duration=1) - Pause for duration seconds.
self.add(mobject) - Add without animation.
self.remove(mobject) - Remove without animation.
self.camera.background_color = "#1e1e2e" - Set background color.
self.play(mob.animate.move_to(UP*2)) - Animate property change.
self.play(mob.animate.set_color(RED)) - Animate color change.
self.play(mob.animate.scale(1.5)) - Animate scaling.""",
    },
    {
        "id": "positioning",
        "text": """Manim Positioning Constants
UP = np.array([0, 1, 0])
DOWN = np.array([0, -1, 0])
LEFT = np.array([-1, 0, 0])
RIGHT = np.array([1, 0, 0])
ORIGIN = np.array([0, 0, 0])
UL = UP + LEFT, UR = UP + RIGHT
DL = DOWN + LEFT, DR = DOWN + RIGHT
Combine: UP*2 + LEFT*3 = point at (-3, 2, 0)
Screen: roughly -7 to +7 horizontal, -4 to +4 vertical""",
    },
    {
        "id": "colors",
        "text": """Manim Colors
WHITE, BLACK, GREY, GREY_A through GREY_E
RED, RED_A through RED_E
BLUE, BLUE_A through BLUE_E
GREEN, GREEN_A through GREEN_E
YELLOW, ORANGE, PURPLE, PINK, TEAL, GOLD, MAROON
Usage: MathTex(...).set_color(YELLOW)
Gradient: mob.set_color_by_gradient(BLUE, GREEN)""",
    },
    {
        "id": "surround_indicate",
        "text": """Manim Indication / Highlighting
SurroundingRectangle(mob, color=YELLOW, buff=0.1) - Box around a mobject.
Indicate(mob) - Flash-highlight animation.
Circumscribe(mob) - Draw a circle around a mobject.
Flash(point) - Flash at a point.
FocusOn(mob) - Focus camera on mobject.
Wiggle(mob) - Wiggle animation.""",
    },
    {
        "id": "parametric_function",
        "text": """Manim ParametricFunction
ParametricFunction(func, t_range=[0, 1, 0.01], color=BLUE)
Where func(t) returns np.array([x, y, 0])
Example: projectile trajectory
ParametricFunction(
    lambda t: np.array([v*np.cos(a)*t, v*np.sin(a)*t - 0.5*g*t**2, 0]),
    t_range=[0, T_flight, 0.01]
)""",
    },
    {
        "id": "numberline",
        "text": """Manim NumberLine
NumberLine(x_range=[-5, 5, 1], length=10, include_numbers=True)
Methods:
  .n2p(number) - Number to point on the line
  .p2n(point) - Point to number
  .add_labels({1: "a", 2: "b"}) - Custom labels""",
    },
]


def ingest_curated_docs() -> None:
    """Ingest hand-curated Manim API documentation into ChromaDB."""
    texts = [chunk["text"] for chunk in MANIM_API_CHUNKS]
    ids = [chunk["id"] for chunk in MANIM_API_CHUNKS]

    add_documents(texts=texts, ids=ids, collection_name="manim_docs")
    logger.info("Ingested %d curated Manim doc chunks", len(texts))


async def ingest_from_urls() -> None:
    """Scrape and ingest Manim docs from official documentation."""
    async with httpx.AsyncClient(timeout=30) as client:
        for url in MANIM_DOC_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    text = _extract_text_from_html(resp.text)
                    chunks = _chunk_text(text, chunk_size=500, overlap=50)

                    ids = [
                        hashlib.md5(f"{url}_{i}".encode()).hexdigest()
                        for i in range(len(chunks))
                    ]

                    add_documents(
                        texts=chunks,
                        ids=ids,
                        metadatas=[{"source": url}] * len(chunks),
                        collection_name="manim_docs",
                    )
                    logger.info("Ingested %d chunks from %s", len(chunks), url)

            except Exception as e:
                logger.warning("Failed to ingest %s: %s", url, e)


def _extract_text_from_html(html: str) -> str:
    """Basic HTML text extraction."""
    # Remove script and style tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ingest_curated_docs()
    print("Curated docs ingested. Run with async for URL-based ingestion.")
