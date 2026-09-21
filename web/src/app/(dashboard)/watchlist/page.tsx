"use client";

import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet, apiPost } from "@/lib/api";

type Profile = {
  ok?: boolean;
  watchlist?: string[];
};

type Explain = {
  ok?: boolean;
  explanation?: {
    score?: number | null;
    direction?: string;
    event_types?: string[];
    summary?: string;
    key_comments?: Record<string, unknown>[];
  };
  sentiment_daily?: Array<{ trade_date: string; score: number; heat: number }>;
};

export default function WatchlistPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [selected, setSelected] = useState("");
  const [explain, setExplain] = useState<Explain | null>(null);
  const [newSym, setNewSym] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    const p = await apiGet<Profile>("/v1/workspace/profile?username=demo");
    setProfile(p);
    const list = p.watchlist ?? [];
    if (!selected && list.length) setSelected(list[0]);
  }, [selected]);

  const loadExplain = useCallback(async (sym: string) => {
    if (!sym) return;
    const ex = await apiGet<Explain>(
      `/v1/watchlist/explain?symbol=${encodeURIComponent(sym)}`,
    );
    setExplain(ex);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await loadProfile();
      if (selected) await loadExplain(selected);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [loadProfile, loadExplain, selected]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (selected) loadExplain(selected);
  }, [selected, loadExplain]);

  const add = async () => {
    if (!newSym.trim()) return;
    await apiPost("/v1/workspace/watch/add", {
      username: "demo",
      symbol: newSym.trim(),
    });
    setNewSym("");
    await refresh();
  };

  const remove = async () => {
    if (!selected) return;
    await apiPost("/v1/workspace/watch/remove", {
      username: "demo",
      symbol: selected,
    });
    setSelected("");
    await refresh();
  };

  const list = profile?.watchlist ?? [];
  const expl = explain?.explanation;

  return (
    <PageChrome
      title="自选股监控"
      description="聚焦自选标的的舆情趋势与可解释摘要（非全市场榜单）。"
      actions={
        <Button variant="outline" size="sm" onClick={refresh}>
          刷新
        </Button>
      }
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      <div className="flex flex-wrap gap-2">
        <Input
          placeholder="添加代码 如 600519.SH"
          value={newSym}
          onChange={(e) => setNewSym(e.target.value)}
          className="max-w-xs"
        />
        <Button onClick={add}>添加</Button>
      </div>
      {list.length === 0 && !loading && (
        <EmptyState message="自选股为空，请先添加标的。" />
      )}
      {list.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <Select value={selected} onValueChange={(v) => v && setSelected(v)}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="选择标的" />
            </SelectTrigger>
            <SelectContent>
              {list.map((s) => (
                <SelectItem key={s} value={s}>{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={remove}>
            移出自选
          </Button>
        </div>
      )}
      {expl && (
        <div className="grid gap-4 md:grid-cols-3">
          <HoverCard className="p-4">
            <p className="text-xs text-muted-foreground">最新情感分</p>
            <p className="text-2xl font-semibold tabular-nums">
              {expl.score != null ? `${expl.score >= 0 ? "+" : ""}${expl.score.toFixed(3)}` : "—"}
            </p>
          </HoverCard>
          <HoverCard className="p-4">
            <p className="text-xs text-muted-foreground">方向</p>
            <p className="text-lg font-medium">{expl.direction ?? "—"}</p>
          </HoverCard>
          <HoverCard className="p-4">
            <p className="text-xs text-muted-foreground">事件类型</p>
            <p className="text-sm">{expl.event_types?.join("、") || "—"}</p>
          </HoverCard>
        </div>
      )}
      {expl?.summary && (
        <HoverCard className="p-4 text-sm leading-relaxed">{expl.summary}</HoverCard>
      )}
      {(explain?.sentiment_daily?.length ?? 0) > 0 && (
        <HoverCard className="p-4">
          <p className="mb-3 text-sm font-medium">舆情情感趋势（简图）</p>
          <div className="flex h-24 items-end gap-1">
            {explain!.sentiment_daily!.slice(-24).map((d, i) => (
              <div
                key={i}
                className="flex-1 rounded-t bg-emerald-500/60 transition-colors hover:bg-emerald-600"
                style={{ height: `${Math.min(100, Math.abs(d.score) * 70 + 15)}%` }}
                title={`${d.trade_date}: ${d.score}`}
              />
            ))}
          </div>
        </HoverCard>
      )}
      {expl?.key_comments?.length ? (
        <HoverCard className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <th className="p-3">平台</th>
                <th className="p-3">标题</th>
                <th className="p-3">分</th>
              </tr>
            </thead>
            <tbody>
              {expl.key_comments.slice(0, 12).map((c, i) => (
                <tr key={i} className="border-b border-border/50 transition-colors hover:bg-muted/30">
                  <td className="p-3">{String(c.platform ?? "—")}</td>
                  <td className="max-w-md truncate p-3">{String(c.title ?? c.summary ?? "—")}</td>
                  <td className="p-3 font-mono text-xs">{String(c.ai_score ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </HoverCard>
      ) : (
        selected && <EmptyState message="暂无关键评论样本。" />
      )}
    </PageChrome>
  );
}
