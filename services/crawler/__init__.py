from services.crawler.service import BatchCrawlResult, CrawlResult, process_document, process_documents
from services.crawler.url_generator import generate_scp_urls

__all__ = [
    "BatchCrawlResult",
    "CrawlResult",
    "generate_scp_urls",
    "process_document",
    "process_documents",
]
