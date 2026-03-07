from services.pipeline import scheduler


def test_run_scheduled_incremental_job_success(monkeypatch) -> None:
    called = {"count": 0}
    monkeypatch.setattr(
        scheduler,
        "run_incremental_pipeline",
        lambda: called.update({"count": called["count"] + 1}) or "ok",
    )
    scheduler.run_scheduled_incremental_job(max_retries=1)
    assert called["count"] == 1


def test_run_scheduled_incremental_job_retries(monkeypatch) -> None:
    called = {"count": 0}

    def flaky():
        called["count"] += 1
        if called["count"] < 2:
            raise RuntimeError("fail once")
        return "ok"

    monkeypatch.setattr(scheduler, "run_incremental_pipeline", flaky)
    monkeypatch.setattr(scheduler.time, "sleep", lambda _: None)

    scheduler.run_scheduled_incremental_job(max_retries=2)
    assert called["count"] == 2
