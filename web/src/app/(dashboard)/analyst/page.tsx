"use client";

import { useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";

type AnalystRes = {
  ok?: boolean;
  has_multi_agent?: boolean;
  multi_agent_rows?: Array<Record<string, unknown>>;
  all_signals_count?: number;
  comparison_rows?: Array<Record<string, unknown>>;
  comparison_path?: string | null;
};

function parseJsonField(raw: unknown): Record<string, unknown> {
  if (typeof raw === "object" && raw !== null) return raw as Record<string, unknown>;
  if (typeof raw === "string" && raw.trim()) {
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return {};
    }
  }
  return {};
}

export default function AnalystPage() {
  const [data, setData] = useState<AnalystRes | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<AnalystRes>("/v1/analyst");
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const latest = data?.multi_agent_rows?.slice(-1)[0];
  const scores = latest ? parseJsonField(latest.analyst_scores) : {};
  const confidences = latest ? parseJsonField(latest.analyst_confidences) : {};

  return (
    <PageChrome
      title="分析师辩论"
      description="多 Agent 共识评分对比；数据来自 signal_history.jsonl 与可选 backtest_comparison.csv。"
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !data?.has_multi_agent && (
        <EmptyState
          message={`暂无多 Agent 字段（共 ${data?.all_signals_count ?? 0} 条信号）。请在 settings.yaml 启用 analysis.enabled 并运行 pipeline，或执行 backtest --multi-agent。`}
        />
      )}
      {latest && (
        <div className="grid gap-4 md:grid-cols-3">
          <HoverCard className="p-4 md:col-span-3">
            <p className="text-xs text-muted-foreground">共识 · {String(latest.symbol ?? "")}</p>
            <p className="text-2xl font-semibold">
              {String(latest.consensus_score ?? latest.score ?? "—")}
            </p>
            <p className="text-sm text-muted-foreground">
              方向 {String(latest.consensus_direction ?? latest.action ?? "—")} · 置信度{" "}
              {String(latest.confidence ?? "—")}
            </p>
          </HoverCard>
          {Object.entries(scores).map(([name, score]) => (
            <HoverCard key={name} className="p-4">
              <p className="text-sm font-medium">{name}</p>
              <p className="text-xl tabular-nums">{String(score)}</p>
              <p className="text-xs text-muted-foreground">
                置信 {String(confidences[name] ?? "—")}
              </p>
            </HoverCard>
          ))}
        </div>
      )}
      {(data?.comparison_rows?.length ?? 0) > 0 && (
        <HoverCard className="overflow-x-auto p-0">
          <p className="border-b p-3 text-sm font-medium">回测对比</p>
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs">
              <tr>
                {Object.keys(data!.comparison_rows![0]).map((k) => (
                  <th key={k} className="p-2">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data!.comparison_rows!.map((row, i) => (
                <tr key={i} className="border-t hover:bg-muted/30">
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="p-2 font-mono text-xs">{String(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data?.comparison_path && (
            <p className="p-2 font-mono text-[10px] text-muted-foreground">
              {data.comparison_path}
            </p>
          )}
        </HoverCard>
      )}
    </PageChrome>
  );
}
