import os
import tempfile
from scraper import NewsManager


def test_hash_deterministic_and_unique():
    nm = NewsManager()
    e1 = {"url": "http://example.com/a", "headline": "Title A", "published": "2025-09-06T00:00:00"}
    e2 = {"url": "http://example.com/a", "headline": "Title A", "published": "2025-09-06T00:00:00"}
    e3 = {"url": "http://example.com/b", "headline": "Title B", "published": "2025-09-06T00:00:00"}
    h1 = nm.generate_hash(e1)
    h2 = nm.generate_hash(e2)
    h3 = nm.generate_hash(e3)
    assert h1 == h2
    assert h1 != h3
