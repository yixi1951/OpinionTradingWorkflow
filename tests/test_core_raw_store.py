from __future__ import annotations

from opinion_trading.core.raw_store import RawPostCsvStore, validate_row_schema


def test_validate_row_schema_valid():
    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "000001.SZ",
        "title": "Test",
        "content": "Some content",
        "keyword_score": 0.5,
        "ai_score": 0.3,
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 0)
    assert violations == []


def test_validate_row_schema_missing_required():
    row = {"trade_date": "", "platform": "guba", "symbol": ""}
    violations = validate_row_schema(row, 5)
    assert any("required field 'trade_date'" in v for v in violations)
    assert any("required field 'symbol'" in v for v in violations)


def test_validate_row_schema_wrong_type():
    row = {
        "trade_date": "2026-06-17",
        "platform": "guba",
        "symbol": "000001.SZ",
        "keyword_score": "not_a_number",
        "capture_status": "success",
    }
    violations = validate_row_schema(row, 1)
    assert any("keyword_score" in v for v in violations)


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
