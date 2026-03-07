from __future__ import annotations


def generate_scp_urls(start: int, end: int) -> list[str]:
    if start < 1 or end < start:
        raise ValueError("Invalid SCP range")

    urls: list[str] = []
    for number in range(start, end + 1):
        suffix = f"{number:03d}" if number < 1000 else str(number)
        urls.append(f"https://scp-wiki.wikidot.com/scp-{suffix}")
    return urls
