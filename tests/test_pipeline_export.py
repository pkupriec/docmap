from __future__ import annotations

import pytest

from services.pipeline import export


@pytest.fixture(autouse=True)
def _restore_export_registry(monkeypatch):
    original = dict(export._PROVIDERS)
    export._PROVIDERS.clear()
    monkeypatch.delenv("DOCMAP_EXPORTER", raising=False)
    yield
    export._PROVIDERS.clear()
    export._PROVIDERS.update(original)


def test_export_is_deterministic_noop_without_provider() -> None:
    assert export.configured_export_items() == ()
    assert export.run_configured_export(mode="incremental") == ()


def test_registered_provider_declares_and_executes_same_items(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    events: list[tuple[str, str, str | None]] = []
    export.register_export_provider(
        export.ExportProvider(
            name="test",
            items=("documents", "locations"),
            export_item=lambda item, mode: calls.append((item, mode)),
        )
    )
    monkeypatch.setenv("DOCMAP_EXPORTER", "test")

    assert export.configured_export_items() == ("documents", "locations")
    completed = export.run_configured_export(
        mode="incremental",
        start_index=1,
        on_item=lambda item, status, error: events.append((item, status, error)),
    )

    assert completed == ("locations",)
    assert calls == [("locations", "incremental")]
    assert events == [
        ("locations", "started", None),
        ("locations", "succeeded", None),
    ]


def test_unknown_configured_provider_fails_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("DOCMAP_EXPORTER", "missing")

    with pytest.raises(RuntimeError, match="not installed"):
        export.configured_export_items()
