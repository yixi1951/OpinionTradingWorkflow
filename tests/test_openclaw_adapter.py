from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from opinion_trading.core.openclaw_adapter import OpenClawClient  # noqa: E402


class OpenClawAdapterTests(unittest.TestCase):
    def test_score_texts_posts_payload_and_returns_scores(self) -> None:
        client = OpenClawClient(
            base_url="http://127.0.0.1:18080", token="demo-token", timeout=3
        )

        response = MagicMock()
        response.json.return_value = {"scores": [0.4, -0.1]}
        response.raise_for_status.return_value = None

        with patch(
            "opinion_trading.core.openclaw_adapter.requests.post", return_value=response
        ) as mock_post:
            scores = client.score_texts(["利好", "风险"])

        self.assertEqual(scores, [0.4, -0.1])
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer demo-token")
        self.assertEqual(kwargs["json"], {"texts": ["利好", "风险"]})
        self.assertTrue(args[0].endswith("/api/v1/sentiment"))

    def test_is_configured_requires_base_url(self) -> None:
        client = OpenClawClient(base_url=None, token=None)
        self.assertFalse(client.is_configured())


if __name__ == "__main__":
    unittest.main()
