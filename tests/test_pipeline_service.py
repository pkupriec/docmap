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
        lambda limit=5000: type(
            "G",
            (),
            {"processed": 6, "linked": 4, "unresolved": 2},
        )(),
    )
    monkeypatch.setattr(service, "rebuild_analytics", lambda: {"bi_documents": 1})
    monkeypatch.setattr(service, "export_all_bi_tables", lambda mode="incremental": None)

    result = service.run_incremental_pipeline(target_urls=["u1", "u2"])
    assert result.crawled_urls == 2
    assert result.extracted_snapshots == 2
    assert result.normalized_mentions == 3
    assert result.geocoded_mentions == 4


def test_run_full_pipeline_uses_canonical_range(monkeypatch) -> None:
    monkeypatch.setattr(service, "generate_scp_urls", lambda start, end: ["u1", "u2"])
    monkeypatch.setattr(
        service,
        "run_incremental_pipeline",
        lambda target_urls=None: type(
            "P",
            (),
            {
                "run_id": "r1",
                "crawled_urls": len(target_urls or []),
                "extracted_snapshots": 0,
                "normalized_mentions": 0,
                "geocoded_mentions": 0,
            },
        )(),
    )

    result = service.run_full_pipeline()
    assert result.crawled_urls == 2
