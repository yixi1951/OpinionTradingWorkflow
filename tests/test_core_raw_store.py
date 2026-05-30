from __future__ import annotations

from opinion_trading.core.raw_store import RawPostCsvStore


def test_save_partitioned_rows_and_failures(tmp_path):
    store = RawPostCsvStore(str(tmp_path))
    rows = [
        {
            "trade_date": "2026-05-30",
            "platform": "guba",
            "symbol": "600519.SH",
            "title": "T1",
            "content": "Content 1",
            "url": "http://example.com/1",
            "source_page": "page1",
            "fetch_time": "2026-05-30T00:00:00",
            "capture_status": "success",
        },
        {
            "trade_date": "2026-05-30",
            "platform": "weibo",
            "symbol": "600519.SH",
            "title": "T2",
            "content": "Content 2",
            "url": "http://example.com/2",
            "source_page": "page2",
            "fetch_time": "2026-05-30T00:00:01",
            "capture_status": "fallback",
            "failure_reason": "timeout",
        },
    ]

    outputs = store.save_partitioned_rows("2026-05-30", rows)
    assert outputs["combined"].exists()
    assert outputs["source:guba"].exists()
    assert outputs["source:weibo"].exists()

    failure_outputs = store.save_failure_logs("2026-05-30", rows)
    assert failure_outputs["combined"].exists()
    assert failure_outputs["source:weibo"].exists()

    csv_text = outputs["combined"].read_text(encoding="utf-8-sig")
    assert "summary" in csv_text
    assert "T1" in csv_text
