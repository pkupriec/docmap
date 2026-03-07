from services.pipeline import service


def test_run_incremental_pipeline_orchestrates(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "process_documents",
        lambda urls: type(
            "R",
            (),
            {"processed": len(urls), "succeeded": len(urls), "failed": 0},
        )(),
    )
    monkeypatch.setattr(service, "process_pending_snapshots", lambda limit=1000: ["s1", "s2"])
    monkeypatch.setattr(service, "normalize_pending_mentions", lambda limit=5000: 3)
    monkeypatch.setattr(
        service,
        "process_pending_mentions",
        lambda limit=5000: type("G", (), {"linked": 4})(),
    )
    monkeypatch.setattr(service, "rebuild_analytics", lambda: {"bi_documents": 1})
    monkeypatch.setattr(service, "export_all_bi_tables", lambda mode="incremental": None)

    result = service.run_incremental_pipeline(target_urls=["u1", "u2"])
    assert result.crawled_urls == 2
    assert result.extracted_snapshots == 2
    assert result.normalized_mentions == 3
    assert result.geocoded_mentions == 4
