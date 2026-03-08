from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import Tag


def extract_title(raw_html: str) -> str | None:
    soup = BeautifulSoup(raw_html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def extract_clean_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")

    for selector in [
        "script",
        "style",
        "noscript",
        "iframe",
        "nav",
        "aside",
        "footer",
        ".sidebar",
        ".page-options-bottom",
        ".creditRate",
        ".rate-box-with-credit-button",
        ".page-tags",
        ".licensebox",
        ".footer-wikiwalk-nav",
        ".pager",
        "#side-bar",
    ]:
        for tag in soup.select(selector):
            tag.decompose()

    root = soup.select_one("#page-content") or soup.body or soup
    _remove_probable_ui_noise(root)

    text = root.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _remove_probable_ui_noise(root: Tag) -> None:
    keywords = (
        "sidebar",
        "footer",
        "nav",
        "menu",
        "tag-list",
        "pager",
        "rating",
        "edit",
        "metadata",
    )

    for tag in list(root.find_all(True)):
        attrs = tag.attrs if isinstance(tag.attrs, dict) else {}

        class_attr = attrs.get("class", [])
        if isinstance(class_attr, str):
            class_names = [class_attr]
        elif isinstance(class_attr, (list, tuple)):
            class_names = [str(item) for item in class_attr if item]
        else:
            class_names = []

        classes = " ".join(class_names).lower()
        element_id = str(attrs.get("id") or "").lower()
        if any(keyword in classes or keyword in element_id for keyword in keywords):
            tag.decompose()
