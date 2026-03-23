from __future__ import annotations

import random
from datetime import date
from typing import Dict


class PlatformSentimentProvider:
    """Stub provider that mimics platform sentiment API results."""

    def fetch(self, platform: str, symbol: str, trade_date: date) -> Dict[str, float]:
        seed = f"{platform}-{symbol}-{trade_date.isoformat()}"
        rng = random.Random(seed)

        sentiment = rng.uniform(-1.0, 1.0)
        post_count = rng.randint(50, 600)

        return {
            "sentiment_score": sentiment,
            "post_count": post_count,
            "source": f"stub://{platform}",
        }
