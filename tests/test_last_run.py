from opinion_trading.core.last_run import (
    format_last_run_caption,
    load_last_run,
    save_last_run,
)


def test_save_and_load_last_run(tmp_path):
    path = save_last_run(
        tmp_path,
        mode="refresh_picks_from_raw",
        picks_path=str(tmp_path / "realtime_picks_x.csv"),
        raw_rows=10,
        symbols=3,
        note="test",
    )
    assert path.exists()
    meta = load_last_run(tmp_path)
    assert meta["mode"] == "refresh_picks_from_raw"
    assert meta["symbols"] == 3
    caption = format_last_run_caption(meta, lang="zh")
    assert "只读上次结果" in caption
