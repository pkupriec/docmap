from __future__ import annotations

from pathlib import Path


PROMPT_PATH = Path(__file__).parent / "prompts" / "location_extraction_prompt.md"


def load_base_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_extraction_prompt(text: str) -> str:
    base_prompt = load_base_prompt()
    return (
        f"{base_prompt}\n\n"
        "Text to analyze:\n"
        "<BEGIN_TEXT>\n"
        f"{text}\n"
        "<END_TEXT>\n\n"
        "Return only valid JSON."
    )
