from services.analytics import bigquery_exporter


def test_export_table_to_bigquery_full(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class DummyClient:
        def get_dataset(self, dataset_id):
            return dataset_id

    monkeypatch.setenv("GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("BIGQUERY_DATASET", "ds")
    monkeypatch.setattr(bigquery_exporter, "get_bigquery_client", lambda: DummyClient())
    monkeypatch.setattr(bigquery_exporter, "_fetch_postgres_rows", lambda table: [{"document_id": "1"}])
    monkeypatch.setattr(
        bigquery_exporter,
        "_load_rows",
        lambda client, table_id, rows, write_disposition, location: calls.update(
            {
                "table_id": table_id,
                "rows": rows,
                "write_disposition": write_disposition,
                "location": location,
            }
        ),
    )

    bigquery_exporter.export_table_to_bigquery("bi_documents", mode="full")

    assert calls["table_id"] == "proj.ds.bi_documents"
    assert calls["write_disposition"] == "WRITE_TRUNCATE"


def test_export_table_to_bigquery_incremental(monkeypatch) -> None:
    events: list[str] = []

    class DummyClient:
        def get_dataset(self, dataset_id):
            return dataset_id

    monkeypatch.setenv("GCP_PROJECT_ID", "proj")
    monkeypatch.setenv("BIGQUERY_DATASET", "ds")
    monkeypatch.setattr(bigquery_exporter, "get_bigquery_client", lambda: DummyClient())
    monkeypatch.setattr(
        bigquery_exporter,
        "_fetch_postgres_rows",
        lambda table: [{"document_id": "1", "location_id": "2", "mention_count": 1}],
    )
    monkeypatch.setattr(
        bigquery_exporter,
        "_load_rows",
        lambda client, table_id, rows, write_disposition, location: events.append(
            f"load:{table_id}:{write_disposition}"
        ),
    )
    monkeypatch.setattr(bigquery_exporter, "_ensure_target_table", lambda client, target, staging: events.append("ensure_target"))
    monkeypatch.setattr(
        bigquery_exporter,
        "_merge_from_staging",
        lambda client, target, staging, table_name, location: events.append("merge"),
    )

    bigquery_exporter.export_table_to_bigquery("bi_document_locations", mode="incremental")
    assert any(event.startswith("load:proj.ds.bi_document_locations__staging") for event in events)
    assert "ensure_target" in events
    assert "merge" in events


def test_export_all_bi_tables_includes_location_hierarchy(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(bigquery_exporter, "export_table_to_bigquery", lambda table_name, mode="full": seen.append(table_name))

    bigquery_exporter.export_all_bi_tables(mode="full")

    assert seen == [
        "bi_documents",
        "bi_locations",
        "bi_document_locations",
        "bi_location_hierarchy",
    ]
