from __future__ import annotations

from pathlib import Path
import logging


PROMPT_PATH = Path(__file__).parent / "prompts" / "location_extraction_prompt.md"
logger = logging.getLogger(__name__)


def load_base_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    logger.debug("extractor.prompt_loaded path=%s chars=%s", PROMPT_PATH, len(text))
    return text


def build_extraction_prompt(text: str) -> str:
    base_prompt = load_base_prompt()
    prompt = (
        f"{base_prompt}\n\n"
        "Text to analyze:\n"
        "<BEGIN_TEXT>\n"
        f"{text}\n"
        "<END_TEXT>\n\n"
        "Return only valid JSON."
    )
    logger.info("extractor.prompt_built input_chars=%s prompt_chars=%s", len(text), len(prompt))
    return prompt
