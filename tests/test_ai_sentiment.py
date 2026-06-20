from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from opinion_trading.core.ai_sentiment import AISentimentAnalyzer  # noqa: E402


def test_score_texts_chunks_openclaw_calls() -> None:
    analyzer = AISentimentAnalyzer()
    analyzer.openclaw = MagicMock()
    analyzer.openclaw.is_configured.return_value = True
    analyzer.openclaw.score_texts.side_effect = [
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6],
    ]

    with patch.dict(os.environ, {"OPENCLAW_BATCH_SIZE": "4"}, clear=False):
        scores = analyzer.score_texts([f"t{i}" for i in range(6)])

    assert scores == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert analyzer.openclaw.score_texts.call_count == 2
