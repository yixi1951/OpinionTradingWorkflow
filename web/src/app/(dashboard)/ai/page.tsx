"use client";

import { useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";

type RawSummary = {
  ok?: boolean;
  total?: number;
  llm_scored?: number;
  ai_relevant?: number;
  capture_success?: number;
  score_source_counts?: Array<{ score_source: string; count: number }>;
  platform_capture?: Array<Record<string, unknown>>;
  drop_reasons?: Array<{ reason: string; count: number }>;
  samples?: Array<Record<string, unknown>>;
  source_path?: string;
};

export default function AiPipelinePage() {
  const [data, setData] = useState<RawSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<RawSummary>("/v1/raw/summary");
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const total = data?.total ?? 0;

  return (
    <PageChrome
      title="AI 采集与筛选"
      description="LLM 相关度筛查与情感打分；展示 score_source 与采集成功率。"
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !data?.ok && (
        <EmptyState message="暂无原始帖数据，请先运行 daily 采集。" />
      )}
      {data?.ok && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "原始帖", value: total },
              {
                label: "LLM 打分",
                value: total
                  ? `${data.llm_scored ?? 0} (${Math.round(((data.llm_scored ?? 0) / total) * 100)}%)`
                  : "0",
              },
              {
                label: "AI 相关",
                value: total
                  ? `${data.ai_relevant ?? 0} (${Math.round(((data.ai_relevant ?? 0) / total) * 100)}%)`
                  : "0",
              },
              {
                label: "采集成功",
                value: total
                  ? `${data.capture_success ?? 0} (${Math.round(((data.capture_success ?? 0) / total) * 100)}%)`
                  : "0",
              },
            ].map((m) => (
              <HoverCard key={m.label} className="p-4">
                <p className="text-xs text-muted-foreground">{m.label}</p>
                <p className="text-xl font-semibold">{m.value}</p>
              </HoverCard>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <HoverCard className="overflow-x-auto p-0">
              <p className="border-b p-3 text-sm font-medium">score_source 分布</p>
              <table className="w-full text-sm">
                <tbody>
                  {(data.score_source_counts ?? []).map((r, i) => (
                    <tr key={i} className="border-t hover:bg-muted/30">
                      <td className="p-2">{r.score_source}</td>
                      <td className="p-2 text-right font-mono">{r.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </HoverCard>
            <HoverCard className="overflow-x-auto p-0">
              <p className="border-b p-3 text-sm font-medium">平台 × 采集状态</p>
              <pre className="max-h-48 overflow-auto p-3 text-xs">
                {JSON.stringify(data.platform_capture ?? [], null, 2)}
              </pre>
            </HoverCard>
          </div>
          {(data.drop_reasons?.length ?? 0) > 0 && (
            <HoverCard className="p-4">
              <p className="mb-2 text-sm font-medium">AI 剔除原因 Top</p>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {data.drop_reasons!.map((d, i) => (
                  <li key={i}>{d.reason}: {d.count}</li>
                ))}
              </ul>
            </HoverCard>
          )}
          <HoverCard className="overflow-x-auto p-0">
            <p className="border-b p-3 text-sm font-medium">相关帖样例</p>
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs">
                <tr>
                  <th className="p-2">代码</th>
                  <th className="p-2">平台</th>
                  <th className="p-2">标题</th>
                  <th className="p-2">分</th>
                </tr>
              </thead>
              <tbody>
                {(data.samples ?? []).map((row, i) => (
                  <tr key={i} className="border-t transition-colors hover:bg-muted/30">
                    <td className="p-2 font-mono text-xs">{String(row.symbol ?? "")}</td>
                    <td className="p-2">{String(row.platform ?? "")}</td>
                    <td className="max-w-xs truncate p-2">{String(row.title ?? "")}</td>
                    <td className="p-2 font-mono text-xs">{String(row.ai_score ?? "")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </HoverCard>
          {data.source_path && (
            <p className="font-mono text-[10px] text-muted-foreground">{data.source_path}</p>
          )}
        </>
      )}
    </PageChrome>
  );
}
