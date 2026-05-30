from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Protocol

from opinion_trading.core.models import OpinionSnapshot


class SentimentProvider(Protocol):
    def fetch(self, platform: str, symbol: str, trade_date: date) -> Dict[str, float]:
        ...


class SentimentCollectionSkill:
    def __init__(self, provider: SentimentProvider) -> None:
        self.provider = provider

    def collect_for_days(
        self, symbols: List[str], platforms: List[str], trade_date: date, lookback_days: int = 1
    ) -> List[OpinionSnapshot]:
        snapshots: List[OpinionSnapshot] = []

        for offset in range(lookback_days, -1, -1):
            d = trade_date - timedelta(days=offset)
            for symbol in symbols:
                for platform in platforms:
                    row = self.provider.fetch(platform=platform, symbol=symbol, trade_date=d)
                    snapshots.append(
                        OpinionSnapshot(
                            timestamp=datetime.now(),
                            trade_date=d,
                            platform=platform,
                            symbol=symbol,
                            sentiment_score=float(row["sentiment_score"]),
                            post_count=int(row["post_count"]),
                            source=str(row["source"]),
                        )
                    )

        return snapshots
