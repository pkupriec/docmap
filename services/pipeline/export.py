from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


ExportItemCallback = Callable[[str, str, str | None], None]
ExportItemHandler = Callable[[str, str], None]


@dataclass(frozen=True)
class ExportProvider:
    name: str
    items: tuple[str, ...]
    export_item: ExportItemHandler


_PROVIDERS: dict[str, ExportProvider] = {}


def register_export_provider(provider: ExportProvider) -> None:
    """Register an optional exporter during application bootstrap."""
    if not provider.name.strip():
        raise ValueError("export provider name is required")
    if len(set(provider.items)) != len(provider.items):
        raise ValueError(f"export provider {provider.name!r} has duplicate items")
    _PROVIDERS[provider.name] = provider


def configured_export_provider() -> ExportProvider | None:
    name = os.getenv("DOCMAP_EXPORTER", "").strip().lower()
    if not name:
        return None
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise RuntimeError(f"Configured export provider is not installed: {name}")
    return provider


def configured_export_items() -> tuple[str, ...]:
    provider = configured_export_provider()
    return provider.items if provider else ()


def run_configured_export(
    *,
    mode: str,
    on_item: ExportItemCallback | None = None,
    start_index: int = 0,
) -> tuple[str, ...]:
    provider = configured_export_provider()
    if provider is None:
        return ()

    start_index = min(max(start_index, 0), len(provider.items))
    selected = provider.items[start_index:]
    for item in selected:
        if on_item:
            on_item(item, "started", None)
        try:
            provider.export_item(item, mode)
        except Exception as exc:
            if on_item:
                on_item(item, "failed", str(exc))
            raise
        if on_item:
            on_item(item, "succeeded", None)
    return selected
