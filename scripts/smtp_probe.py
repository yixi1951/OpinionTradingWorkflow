#!/usr/bin/env python3
"""SMTP / email delivery probe (sink or real SMTP)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opinion_trading.core.email_service import send_transactional_email
from opinion_trading.core.env_bootstrap import load_dotenv_if_present


def main() -> int:
    load_dotenv_if_present(ROOT)
    parser = argparse.ArgumentParser(description="Probe transactional email delivery")
    parser.add_argument("--to", default="ops@localhost", help="Recipient address")
    parser.add_argument(
        "--subject", default="OpenClaw SMTP probe", help="Email subject"
    )
    args = parser.parse_args()
    result = send_transactional_email(
        args.to,
        args.subject,
        "This is a delivery probe from scripts/smtp_probe.py.\n"
        "If SMTP_HOST is unset, the message was written to EMAIL_SINK_PATH.",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
