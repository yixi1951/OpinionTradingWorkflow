"use client";

import { cn } from "@/lib/utils";
import type { StockQuote } from "@/lib/types";

function formatPrice(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPct(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function StockSymbolCell({
  symbol,
  name,
  className,
}: {
  symbol?: string;
  name?: string;
  className?: string;
}) {
  const code = symbol?.trim() || "—";
  const displayName = name?.trim();
  return (
    <div className={cn("min-w-[120px]", className)}>
      <div className="font-medium leading-tight text-foreground">
        {displayName || code}
      </div>
      {displayName && (
        <div className="font-mono text-xs text-muted-foreground">{code}</div>
      )}
      {!displayName && (
        <div className="text-xs text-muted-foreground">名称未知</div>
      )}
    </div>
  );
}

export function StockQuoteInline({ quote }: { quote?: StockQuote }) {
  if (!quote) {
    return <span className="text-xs text-muted-foreground">行情不可用</span>;
  }
  if (!quote.ok && quote.error) {
    return (
      <span className="text-xs text-muted-foreground" title={quote.error}>
        行情不可用
      </span>
    );
  }
  const pct = quote.change_pct;
  const tone =
    pct == null || pct === 0
      ? "text-muted-foreground"
      : pct > 0
        ? "text-emerald-700"
        : "text-red-600";
  const delayed = quote.delayed;
  const status = quote.market_status;
  const statusLabel =
    status === "open"
      ? delayed
        ? "延时"
        : "盘中"
      : status === "lunch"
        ? "午休"
        : "已收盘";

  return (
    <div className="space-y-0.5 text-right tabular-nums">
      <div className="text-sm font-medium">{formatPrice(quote.last_price)}</div>
      <div className={cn("text-xs font-medium", tone)}>
        {formatPct(quote.change_pct)}
        {quote.change_amount != null && (
          <span className="ml-1 text-muted-foreground">
            ({quote.change_amount > 0 ? "+" : ""}
            {quote.change_amount.toFixed(2)})
          </span>
        )}
      </div>
      <div className="text-[10px] text-muted-foreground">
        {statusLabel}
        {quote.note ? ` · ${quote.note}` : ""}
        {quote.as_of ? ` · ${quote.as_of.slice(0, 16).replace("T", " ")}` : ""}
      </div>
    </div>
  );
}
