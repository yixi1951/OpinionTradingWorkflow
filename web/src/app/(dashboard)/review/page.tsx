"use client";

import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";

type Profile = { watchlist?: string[] };

type Review = {
  ok?: boolean;
  sentiment_daily?: Array<{ trade_date: string; score: number }>;
  prices?: Array<{ date: string; close: number }>;
  explanation?: { summary?: string; key_comments?: Record<string, unknown>[] };
  score_return_corr?: number | null;
};

export default function ReviewPage() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState("");
  const [lookback, setLookback] = useState(90);
  const [data, setData] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSymbols = useCallback(async () => {
    const p = await apiGet<Profile>("/v1/workspace/profile?username=demo");
    const list = p.watchlist?.length ? p.watchlist : ["600519.SH"];
    setSymbols(list);
    if (!symbol) setSymbol(list[0]);
  }, [symbol]);

  const loadReview = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const r = await apiGet<Review>(
        `/v1/review/series?symbol=${encodeURIComponent(symbol)}&lookback_days=${lookback}`,
      );
      setData(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [symbol, lookback]);

  useEffect(() => {
    loadSymbols();
  }, [loadSymbols]);

  useEffect(() => {
    loadReview();
  }, [loadReview]);

  const daily = data?.sentiment_daily ?? [];
  const prices = data?.prices ?? [];

  return (
    <PageChrome
      title="舆情股价复盘"
      description="叠加舆情与收盘价走势，观察信号与价格关系（行情依赖 Yahoo/本地缓存）。"
      actions={
        <Button variant="outline" size="sm" onClick={loadReview}>
          刷新
        </Button>
      }
    >
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label>复盘标的</Label>
          <Select value={symbol} onValueChange={(v) => v && setSymbol(v)}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {symbols.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>回看天数</Label>
          <Select
            value={String(lookback)}
            onValueChange={(v) => setLookback(Number(v))}
          >
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[30, 60, 90, 120, 180].map((d) => (
                <SelectItem key={d} value={String(d)}>{d} 天</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !data?.ok && (
        <EmptyState message="缺少舆情或行情数据，请先运行 daily/realtime。" />
      )}
      {data?.score_return_corr != null && (
        <HoverCard className="p-4">
          <p className="text-xs text-muted-foreground">舆情分 vs 次日收益 相关系数</p>
          <p className="text-2xl font-semibold tabular-nums">
            {data.score_return_corr >= 0 ? "+" : ""}
            {data.score_return_corr.toFixed(3)}
          </p>
        </HoverCard>
      )}
      {(daily.length > 0 || prices.length > 0) && (
        <HoverCard className="p-4">
          <p className="mb-2 text-sm font-medium">双序列简图（归一化展示）</p>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs text-muted-foreground">舆情</p>
              <div className="flex h-20 items-end gap-0.5">
                {daily.slice(-30).map((d, i) => (
                  <div
                    key={i}
                    className="flex-1 bg-sky-500/60"
                    style={{ height: `${Math.abs(d.score) * 60 + 10}%` }}
                  />
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1 text-xs text-muted-foreground">收盘价</p>
              <div className="flex h-20 items-end gap-0.5">
                {prices.slice(-30).map((p, i, arr) => {
                  const min = Math.min(...arr.map((x) => x.close));
                  const max = Math.max(...arr.map((x) => x.close));
                  const h = max > min ? ((p.close - min) / (max - min)) * 100 : 50;
                  return (
                    <div
                      key={i}
                      className="flex-1 bg-amber-500/60"
                      style={{ height: `${h}%` }}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        </HoverCard>
      )}
      {data?.explanation?.summary && (
        <HoverCard className="p-4 text-sm">{data.explanation.summary}</HoverCard>
      )}
    </PageChrome>
  );
}
