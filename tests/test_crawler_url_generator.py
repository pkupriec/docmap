from services.crawler.url_generator import generate_scp_urls


def test_generate_scp_urls_range() -> None:
    urls = generate_scp_urls(1, 3)
    assert urls == [
        "https://scp-wiki.wikidot.com/scp-001",
        "https://scp-wiki.wikidot.com/scp-002",
        "https://scp-wiki.wikidot.com/scp-003",
    ]


def test_generate_scp_urls_over_999() -> None:
    urls = generate_scp_urls(999, 1001)
    assert urls == [
        "https://scp-wiki.wikidot.com/scp-999",
        "https://scp-wiki.wikidot.com/scp-1000",
        "https://scp-wiki.wikidot.com/scp-1001",
    ]
