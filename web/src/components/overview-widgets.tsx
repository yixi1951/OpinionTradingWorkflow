"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, PlayCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HoverCard } from "@/components/hover-card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet, API_BASE } from "@/lib/api";
import type { PickRow, StatusResponse } from "@/lib/types";
import { StockQuoteInline, StockSymbolCell } from "@/components/stock-symbol";
import { PageChrome } from "@/components/page-chrome";

const STORAGE_KEY = "otw-dashboard-widget-order-v1";

type WidgetId =
  | "status"
  | "picks"
  | "alerts"
  | "sentiment"
  | "memory"
  | "run";

const DEFAULT_ORDER: WidgetId[] = [
  "status",
  "picks",
  "alerts",
  "sentiment",
  "memory",
  "run",
];

type Snapshot = {
  ok?: boolean;
  picks?: PickRow[];
  alerts?: unknown[];
  platform_count?: number;
  pipeline?: { total?: number };
};

type SentimentHist = {
  rows?: Array<{ sentiment_score?: number; trade_date?: string }>;
  avg_score?: number | null;
};

type MemorySnippet = {
  rows?: Array<Record<string, unknown>>;
};

function StaticWidget({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full">
      <HoverCard className="relative h-full p-4">{children}</HoverCard>
    </div>
  );
}

function SortableWidget({
  id,
  children,
}: {
  id: WidgetId;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 20 : undefined,
  };
  return (
    <div ref={setNodeRef} style={style} className="h-full">
      <HoverCard className="relative h-full p-4">
        <button
          type="button"
          className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Drag widget"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        {children}
      </HoverCard>
    </div>
  );
}

function healthBadge(status?: string) {
  if (status === "ok" || status === "ready") {
    return <Badge className="bg-emerald-600/15 text-emerald-700">正常</Badge>;
  }
  if (status === "down") {
    return <Badge variant="destructive">离线</Badge>;
  }
  return <Badge variant="secondary">{status ?? "—"}</Badge>;
}

export function OverviewWidgets() {
  const [dndReady, setDndReady] = useState(false);
  const [order, setOrder] = useState<WidgetId[]>(DEFAULT_ORDER);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [sentiment, setSentiment] = useState<SentimentHist | null>(null);
  const [memory, setMemory] = useState<MemorySnippet | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setDndReady(true);
  }, []);

  useEffect(() => {
    if (!dndReady) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as WidgetId[];
        if (Array.isArray(parsed) && parsed.length) setOrder(parsed);
      }
    } catch {
      /* ignore */
    }
  }, [dndReady]);

  const persistOrder = useCallback((next: WidgetId[]) => {
    setOrder(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [st, sn, sh, mem] = await Promise.all([
        apiGet<StatusResponse>("/v1/status"),
        apiGet<Snapshot>("/v1/dashboard/snapshot"),
        apiGet<SentimentHist>("/v1/sentiment/history?limit=40"),
        apiGet<MemorySnippet>("/v1/memory/query?kind=signals&limit=5"),
      ]);
      setStatus(st);
      setSnap(sn);
      setSentiment(sh);
      setMemory(mem);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = order.indexOf(active.id as WidgetId);
    const newIndex = order.indexOf(over.id as WidgetId);
    if (oldIndex < 0 || newIndex < 0) return;
    persistOrder(arrayMove(order, oldIndex, newIndex));
  };

  const spark = useMemo(() => {
    const rows = sentiment?.rows ?? [];
    return rows
      .slice(-12)
      .map((r) => Number(r.sentiment_score ?? 0))
      .filter((n) => !Number.isNaN(n));
  }, [sentiment]);

  const widgetContent: Record<WidgetId, React.ReactNode> = {
    status: (
      <div className="space-y-3 pr-8">
        <p className="text-sm font-medium text-muted-foreground">服务状态</p>
        {status ? (
          <ul className="space-y-2 text-sm">
            {(["api", "collector", "inference", "compute"] as const).map((k) => {
              const raw = status[k];
              const st =
                k === "api"
                  ? raw === "ok" ? "ok" : String(raw)
                  : (raw as { status?: string })?.status;
              return (
                <li key={k} className="flex items-center justify-between gap-2">
                  <span className="capitalize">{k}</span>
                  {healthBadge(st)}
                </li>
              );
            })}
          </ul>
        ) : (
          <LoadingBlock rows={2} />
        )}
        <p className="font-mono text-[10px] text-muted-foreground">{API_BASE}</p>
      </div>
    ),
    picks: (
      <div className="space-y-3 pr-8">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-muted-foreground">选股预览</p>
          <Link href="/picks" className="text-xs text-emerald-700 hover:underline">
            查看全部
          </Link>
        </div>
        {(snap?.picks ?? []).slice(0, 3).map((p, i) => (
          <div key={i} className="flex items-start justify-between gap-3 text-sm">
            <StockSymbolCell symbol={p.symbol} name={p.name} className="flex-1" />
            <div className="shrink-0 text-right">
              <StockQuoteInline quote={p.quote} />
              <div className="mt-1 text-[10px] text-muted-foreground">
                信号 {p.score != null ? Number(p.score).toFixed(3) : "—"}
              </div>
            </div>
          </div>
        ))}
        {!(snap?.picks?.length) && (
          <p className="text-xs text-muted-foreground">暂无实时选股 CSV</p>
        )}
      </div>
    ),
    alerts: (
      <div className="space-y-3 pr-8">
        <p className="text-sm font-medium text-muted-foreground">评分告警</p>
        <p className="text-3xl font-semibold tabular-nums">
          {snap?.alerts?.length ?? 0}
        </p>
        <Link href="/alerts" className="text-xs text-emerald-700 hover:underline">
          配置预警规则
        </Link>
      </div>
    ),
    sentiment: (
      <div className="space-y-3 pr-8">
        <p className="text-sm font-medium text-muted-foreground">舆情均值</p>
        <p className="text-2xl font-semibold tabular-nums">
          {sentiment?.avg_score != null
            ? sentiment.avg_score.toFixed(3)
            : "—"}
        </p>
        <div className="flex h-10 items-end gap-0.5">
          {spark.length ? (
            spark.map((v, i) => (
              <div
                key={i}
                className="flex-1 rounded-sm bg-emerald-500/70 transition-all hover:bg-emerald-600"
                style={{
                  height: `${Math.min(100, Math.abs(v) * 80 + 12)}%`,
                  opacity: 0.35 + (i / spark.length) * 0.65,
                }}
                title={v.toFixed(3)}
              />
            ))
          ) : (
            <span className="text-xs text-muted-foreground">无历史</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          平台数 {snap?.platform_count ?? 0}
        </p>
      </div>
    ),
    memory: (
      <div className="space-y-3 pr-8">
        <p className="text-sm font-medium text-muted-foreground">记忆片段</p>
        <ul className="space-y-2 text-xs text-muted-foreground">
          {(memory?.rows ?? []).map((r, i) => (
            <li key={i} className="truncate">
              {String(r.trade_date ?? "")} · {String(r.symbol ?? "")} ·{" "}
              {String(r.action ?? "")}
            </li>
          ))}
        </ul>
        {!memory?.rows?.length && <p className="text-xs">暂无 signal 记忆</p>}
        <Link href="/memory" className="text-xs text-emerald-700 hover:underline">
          打开记忆库
        </Link>
      </div>
    ),
    run: (
      <div className="flex h-full flex-col justify-between gap-4 pr-8">
        <div>
          <p className="text-sm font-medium text-muted-foreground">运行日线</p>
          <p className="mt-2 text-xs text-muted-foreground">
            原始帖 {snap?.pipeline?.total ?? 0} 条（最新 CSV）
          </p>
        </div>
        <Link
          href="/run"
          className="inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-shadow hover:shadow-md"
        >
          <PlayCircle className="mr-2 h-4 w-4" />
          前往运行
        </Link>
      </div>
    ),
  };

  return (
    <PageChrome
      title="总览"
      description="可拖拽排序的组件面板 — 布局保存在本机 localStorage。"
      actions={
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          刷新
        </Button>
      }
    >
      {loading && !status && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !error && !status && (
        <EmptyState message="无法加载总览数据。" />
      )}
      {dndReady ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={order} strategy={rectSortingStrategy}>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {order.map((id) => (
                <SortableWidget key={id} id={id}>
                  {widgetContent[id]}
                </SortableWidget>
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {order.map((id) => (
            <StaticWidget key={id}>{widgetContent[id]}</StaticWidget>
          ))}
        </div>
      )}
    </PageChrome>
  );
}
