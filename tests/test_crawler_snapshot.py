from services.crawler.snapshot import should_create_snapshot


def test_should_create_snapshot_first_time() -> None:
    assert should_create_snapshot("new text", None) is True


def test_should_create_snapshot_when_changed() -> None:
    assert should_create_snapshot("new text", "old text") is True


def test_should_not_create_snapshot_when_unchanged() -> None:
    assert should_create_snapshot("same text", "same text") is False


def test_should_create_snapshot_when_forced() -> None:
    assert should_create_snapshot("same text", "same text", resnapshot=True) is True
