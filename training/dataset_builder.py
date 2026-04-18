#!/usr/bin/env python3
"""
DIME — Dataset Builder.

Constructs training data from JEE question PDFs:
1. Extract question-solution pairs from PDFs (PyMuPDF)
2. Capture diagram regions as images
3. Generate scene JSON using Claude/GPT API (one-time batch cost)
4. Split into train/val/test

Usage:
    python training/dataset_builder.py \
        --questions-dir data/questions \
        --solutions-dir data/solutions \
        --output-dir data/training \
        --split-ratio 0.8 0.1 0.1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract question-solution pairs from a PDF.

    Returns list of dicts with:
        - text: extracted text
        - images: list of image paths (diagrams)
        - page_number: source page
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
        return []

    doc = fitz.open(pdf_path)
    entries = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text").strip()
        if not text:
            continue

        # Extract images from page
        images = []
        image_dir = os.path.join(
            os.path.dirname(pdf_path),
            "extracted_images",
            Path(pdf_path).stem,
        )
        os.makedirs(image_dir, exist_ok=True)

        for img_idx, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n >= 5:  # CMYK
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                img_path = os.path.join(
                    image_dir,
                    f"page{page_num + 1}_img{img_idx + 1}.png",
                )
                pix.save(img_path)
                images.append(img_path)
            except Exception as e:
                logger.debug("Failed to extract image: %s", e)

        entries.append(
            {
                "text": text,
                "images": images,
                "page_number": page_num + 1,
                "source_file": os.path.basename(pdf_path),
            }
        )

    doc.close()
    logger.info("Extracted %d pages from %s", len(entries), pdf_path)
    return entries


def parse_questions(entries: list[dict]) -> list[dict]:
    """
    Parse raw page text into individual questions.

    JEE papers typically have questions numbered 1-75 across 3 sections.
    """
    questions = []

    for entry in entries:
        text = entry["text"]

        # Try to split by question numbers
        # Common patterns: "1.", "Q.1", "1)", "(1)"
        parts = re.split(r"(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,2})\s*[.)]\s*", text)

        if len(parts) > 2:
            for i in range(1, len(parts), 2):
                q_num = parts[i]
                q_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if q_text and len(q_text) > 20:
                    questions.append(
                        {
                            "question_number": int(q_num),
                            "question_text": q_text,
                            "images": entry["images"],
                            "source": entry["source_file"],
                            "page": entry["page_number"],
                        }
                    )
        else:
            # Treat whole page as one entry
            if len(text) > 50:
                questions.append(
                    {
                        "question_number": 0,
                        "question_text": text,
                        "images": entry["images"],
                        "source": entry["source_file"],
                        "page": entry["page_number"],
                    }
                )

    logger.info("Parsed %d individual questions", len(questions))
    return questions


def build_brain_training_entry(
    question: dict, scene_json: Optional[dict] = None
) -> dict:
    """
    Build a single Brain training example.

    If scene_json is not provided, creates a placeholder that needs
    to be filled by Claude/GPT API or manually.
    """
    messages = [
        {
            "role": "system",
            "content": "You are an expert JEE teacher. Given a question, produce a structured scene JSON for animation.",
        },
        {
            "role": "user",
            "content": f"Solve this JEE question and produce the scene JSON:\n\n{question['question_text']}",
        },
    ]

    if scene_json:
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(scene_json, indent=2),
            }
        )
    else:
        messages.append(
            {
                "role": "assistant",
                "content": "TODO: Generate scene JSON (use Claude API batch or manual annotation)",
            }
        )

    entry = {"messages": messages}
    if question.get("images"):
        entry["images"] = question["images"][:1]  # First image only

    return entry


def split_dataset(
    data: list[dict],
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split data into train/val/test."""
    import random

    random.seed(42)
    random.shuffle(data)

    n = len(data)
    train_end = int(n * ratios[0])
    val_end = train_end + int(n * ratios[1])

    return data[:train_end], data[train_end:val_end], data[val_end:]


def main():
    parser = argparse.ArgumentParser(description="Build training dataset from JEE PDFs")
    parser.add_argument("--questions-dir", default="data/questions")
    parser.add_argument("--solutions-dir", default="data/solutions")
    parser.add_argument("--output-dir", default="data/training")
    parser.add_argument("--split-ratio", nargs=3, type=float, default=[0.8, 0.1, 0.1])
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Extract from all PDFs
    all_entries = []

    for pdf_dir in [args.questions_dir, args.solutions_dir]:
        if not os.path.exists(pdf_dir):
            logger.warning("Directory not found: %s", pdf_dir)
            continue
        for pdf_file in sorted(Path(pdf_dir).glob("*.pdf")):
            entries = extract_from_pdf(str(pdf_file))
            all_entries.extend(entries)

    # Parse into questions
    questions = parse_questions(all_entries)

    if not questions:
        logger.error("No questions found! Check your PDF files.")
        return

    # Build Brain training entries
    brain_data = [build_brain_training_entry(q) for q in questions]

    # Split
    train, val, test = split_dataset(brain_data, tuple(args.split_ratio))

    # Save
    for name, data in [("train", train), ("val", val), ("test", test)]:
        path = os.path.join(args.output_dir, f"brain_{name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d entries to %s", len(data), path)

    logger.info(
        "✅ Dataset built: %d train, %d val, %d test",
        len(train),
        len(val),
        len(test),
    )
    logger.info(
        "⚠️  Note: Scene JSON entries need to be generated.\n"
        "   Run Claude/GPT API batch conversion or annotate manually.\n"
        "   See training/README.md for instructions."
    )


if __name__ == "__main__":
    main()
