from __future__ import annotations

import hashlib


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def should_create_snapshot(
    new_clean_text: str,
    previous_clean_text: str | None,
    *,
    resnapshot: bool = False,
) -> bool:
    if resnapshot:
        return True
    if previous_clean_text is None:
        return True
    return compute_text_hash(new_clean_text) != compute_text_hash(previous_clean_text)
