"use client";

import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";

type CommentsRes = {
  ok?: boolean;
  message?: string;
  stats?: Record<string, unknown>;
  rows?: Array<Record<string, unknown>>;
};

export default function CommentsPage() {
  const [symbol, setSymbol] = useState("600519.SH");
  const [data, setData] = useState<CommentsRes | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiGet<CommentsRes>(
        `/v1/comments?symbol=${encodeURIComponent(symbol.trim())}&top_n=30&lookback_days=14`,
      );
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PageChrome
      title="评论依据"
      description="选股证据链：近 14 日多源 raw 合并，默认剔除广告/噪声。"
      actions={
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          查询
        </Button>
      }
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-2">
          <Label>标的代码</Label>
          <Input
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-48 font-mono"
          />
        </div>
        <Button onClick={load}>加载</Button>
      </div>
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {data?.stats && (
        <HoverCard className="p-4 font-mono text-xs text-muted-foreground">
          {JSON.stringify(data.stats)}
        </HoverCard>
      )}
      {!loading && data && !data.ok && (
        <EmptyState message={data.message ?? "无评论数据。"} />
      )}
      {(data?.rows?.length ?? 0) > 0 && (
        <HoverCard className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <th className="p-3">类型</th>
                <th className="p-3">平台</th>
                <th className="p-3">标题 / 摘要</th>
                <th className="p-3">分</th>
              </tr>
            </thead>
            <tbody>
              {data!.rows!.map((r, i) => (
                <tr
                  key={i}
                  className="border-t border-border/50 transition-colors hover:bg-emerald-50/50"
                >
                  <td className="p-3">{String(r.kind ?? r.polarity ?? "—")}</td>
                  <td className="p-3">{String(r.platform ?? "—")}</td>
                  <td className="max-w-lg p-3">
                    <p className="line-clamp-2">{String(r.title ?? r.summary ?? r.text ?? "—")}</p>
                  </td>
                  <td className="p-3 font-mono text-xs">{String(r.ai_score ?? r.score ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </HoverCard>
      )}
    </PageChrome>
  );
}
