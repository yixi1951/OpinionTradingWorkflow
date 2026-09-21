"use client";

import { useEffect, useState } from "react";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";

type OpenClawRes = {
  ok?: boolean;
  probe?: { connected?: boolean; message?: string; url?: string };
  summary?: Record<string, unknown>;
  activity_feed?: Array<Record<string, unknown>>;
  latest_picks_path?: string;
};

export default function OpenClawPage() {
  const [data, setData] = useState<OpenClawRes | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<OpenClawRes>("/v1/openclaw/dashboard");
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const connected = data?.probe?.connected;

  return (
    <PageChrome
      title="OpenClaw 实时"
      description="引擎连接状态、AI 打分摘要与活动 feed（只读；探测依赖 OPENCLAW_URL）。"
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {data && (
        <HoverCard className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <p className="text-sm font-medium">OpenClaw 引擎</p>
            <p className="text-xs text-muted-foreground">
              {data.probe?.url ?? data.probe?.message ?? "—"}
            </p>
          </div>
          <Badge
            className={
              connected
                ? "bg-emerald-600/15 text-emerald-800"
                : "bg-amber-500/15 text-amber-900"
            }
          >
            {connected ? "已连接" : "未连接 / 关键词兜底"}
          </Badge>
        </HoverCard>
      )}
      {data?.summary && (
        <HoverCard className="p-4">
          <p className="mb-2 text-sm font-medium">打分摘要</p>
          <pre className="max-h-64 overflow-auto text-xs text-muted-foreground">
            {JSON.stringify(data.summary, null, 2)}
          </pre>
        </HoverCard>
      )}
      {(data?.activity_feed?.length ?? 0) > 0 ? (
        <HoverCard className="overflow-x-auto p-0">
          <p className="border-b p-3 text-sm font-medium">活动 feed</p>
          <table className="w-full text-sm">
            <tbody>
              {data!.activity_feed!.map((row, i) => (
                <tr key={i} className="border-t hover:bg-muted/30">
                  <td className="p-2 font-mono text-xs">
                    {JSON.stringify(row).slice(0, 200)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </HoverCard>
      ) : (
        !loading && <EmptyState message="暂无活动 feed（需要 raw CSV 与选股数据）。" />
      )}
      {data?.latest_picks_path && (
        <p className="font-mono text-[10px] text-muted-foreground">
          {data.latest_picks_path}
        </p>
      )}
    </PageChrome>
  );
}
