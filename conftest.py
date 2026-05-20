import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "scripts"))


@pytest.fixture
def sample_article():
    return {
        "id": "a1b2c3d4e5f6a7b8",
        "title": "Test Article",
        "vendor": "Anthropic",
        "source": "anthropic.com",
        "url": "https://anthropic.com/test",
        "date": "2026-05-20",
        "description": "A test article about AI.",
        "score": 8,
        "scraped_at": "2026-05-20",
    }


@pytest.fixture
def today():
    return date(2026, 5, 20)
