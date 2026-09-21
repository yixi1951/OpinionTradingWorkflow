"use client";

import { useCallback, useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  watchlist?: string[];
  alert_rules?: Array<{
    symbol?: string;
    score_high?: number;
    score_low?: number;
    heat_spike_ratio?: number;
  }>;
  email?: string;
};

type Inbox = { messages?: Array<Record<string, unknown>> };

export default function AlertsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [symbol, setSymbol] = useState("");
  const [scoreHigh, setScoreHigh] = useState(0.35);
  const [scoreLow, setScoreLow] = useState(-0.35);
  const [heatRatio, setHeatRatio] = useState(2);
  const [email, setEmail] = useState("");
  const [runResult, setRunResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = await apiGet<Profile>("/v1/workspace/profile?username=demo");
      setProfile(p);
      const sym = p.watchlist?.[0] ?? "600519.SH";
      setSymbol(sym);
      const rule = p.alert_rules?.find(
        (r) => String(r.symbol).toUpperCase() === sym.toUpperCase(),
      );
      if (rule) {
        setScoreHigh(Number(rule.score_high ?? 0.35));
        setScoreLow(Number(rule.score_low ?? -0.35));
        setHeatRatio(Number(rule.heat_spike_ratio ?? 2));
      }
      setEmail(p.email ?? "");
      const ib = await apiGet<Inbox>("/v1/workspace/inbox?username=demo");
      setInbox(ib);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    await apiPost("/v1/workspace/alerts", {
      username: "demo",
      symbol,
      score_high: scoreHigh,
      score_low: scoreLow,
      heat_spike_ratio: heatRatio,
      email,
    });
    await load();
  };

  const run = async () => {
    const res = await apiPost<{ count?: number }>("/v1/workspace/alerts/run", {
      username: "demo",
    });
    setRunResult(`触发 ${res.count ?? 0} 条预警`);
    await load();
  };

  const symbols = profile?.watchlist?.length
    ? profile.watchlist
    : ["600519.SH"];

  return (
    <PageChrome
      title="信号预警"
      description="情感阈值与热度突增规则；触发后写入站内信（邮件/企微需后端配置）。"
      actions={
        <Button variant="outline" size="sm" onClick={load}>
          刷新
        </Button>
      }
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      <HoverCard className="grid gap-4 p-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>预警标的</Label>
          <Select value={symbol} onValueChange={(v) => v && setSymbol(v)}>
            <SelectTrigger>
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
          <Label>预警邮箱</Label>
          <Input value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>情感分上限</Label>
          <Input
            type="number"
            step="0.05"
            value={scoreHigh}
            onChange={(e) => setScoreHigh(Number(e.target.value))}
          />
        </div>
        <div className="space-y-2">
          <Label>情感分下限</Label>
          <Input
            type="number"
            step="0.05"
            value={scoreLow}
            onChange={(e) => setScoreLow(Number(e.target.value))}
          />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label>热度突增倍数</Label>
          <Input
            type="number"
            step="0.1"
            min={1}
            value={heatRatio}
            onChange={(e) => setHeatRatio(Number(e.target.value))}
          />
        </div>
        <div className="flex flex-wrap gap-2 md:col-span-2">
          <Button onClick={save}>保存规则</Button>
          <Button variant="secondary" onClick={run}>
            立即检查
          </Button>
        </div>
        {runResult && <p className="text-sm text-emerald-700 md:col-span-2">{runResult}</p>}
      </HoverCard>
      <div>
        <h2 className="mb-2 text-sm font-medium">站内信</h2>
        {(inbox?.messages?.length ?? 0) === 0 ? (
          <EmptyState message="暂无站内信。" />
        ) : (
          <HoverCard className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="p-3">时间</th>
                  <th className="p-3">标题</th>
                  <th className="p-3">已读</th>
                </tr>
              </thead>
              <tbody>
                {inbox!.messages!.map((m, i) => (
                  <tr
                    key={i}
                    className="border-t border-border/50 transition-colors hover:bg-muted/30"
                  >
                    <td className="p-3 font-mono text-xs">{String(m.created_at ?? "")}</td>
                    <td className="p-3">{String(m.title ?? m.body ?? "")}</td>
                    <td className="p-3">{m.read ? "是" : "否"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </HoverCard>
        )}
      </div>
    </PageChrome>
  );
}
