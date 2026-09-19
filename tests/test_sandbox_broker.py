from datetime import date
from pathlib import Path

from opinion_trading.core.models import TradeSignal
from opinion_trading.integrations.broker_adapter import (
    SandboxBrokerAdapter,
    get_broker_adapter,
    trade_signals_to_intents,
)


def test_sandbox_dry_run_records_intent(tmp_path: Path) -> None:
    sig = TradeSignal(
        trade_date=date(2026, 6, 17),
        symbol="600519.SH",
        action="BUY",
        confidence=0.8,
        reason="sandbox-smoke",
        platforms=["guba"],
        kelly_fraction=0.1,
    )
    intents = trade_signals_to_intents([sig], dry_run=True)
    broker = get_broker_adapter("sandbox", str(tmp_path))
    assert isinstance(broker, SandboxBrokerAdapter)
    out = broker.submit_intents(intents)
    assert out["count"] == 1
    assert out["dry_run"] is True
    assert out["sandbox"] is True
    assert out["live_order"] is False
    path = Path(str(out["path"]))
    assert path.name.startswith("sandbox_intents_")
    text = path.read_text(encoding="utf-8")
    assert "600519.SH" in text
    assert '"live_order": false' in text
    assert len(broker.recorded) == 1
