"use client";

import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";
import type { SentimentRow } from "@/lib/types";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";

type EvidencePost = {
  platform?: string;
  title?: string;
  ai_score?: number;
  trade_date?: string;
  url?: string;
};

type SentimentResponse = {
  ok: boolean;
  rows: SentimentRow[];
  count: number;
  avg_score: number | null;
  evidence_posts?: EvidencePost[];
  evidence_count?: number;
  lookback_days?: number;
};

function scoreColor(score: number) {
  if (score > 0.15) return "text-emerald-700";
  if (score < -0.15) return "text-rose-600";
  return "text-muted-foreground";
}

export default function SentimentPage() {
  const [symbol, setSymbol] = useState("");
  const [data, setData] = useState<SentimentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async (sym?: string) => {
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams({
        limit: "120",
        evidence_limit: "50",
        lookback_days: "14",
      });
      if (sym?.trim()) q.set("symbol", sym.trim().toUpperCase());
      const res = await apiGet<SentimentResponse>(`/v1/sentiment/history?${q}`);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load sentiment");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <PageChrome
      title="舆情分析"
      description="聚合舆情历史 + 近 14 日去噪后的评论证据（多日 raw）。"
    >
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          load(symbol);
        }}
      >
        <div className="space-y-1">
          <Label htmlFor="symbol">Symbol filter</Label>
          <Input
            id="symbol"
            placeholder="e.g. 600519"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="w-40 font-mono"
          />
        </div>
        <Button type="submit" disabled={loading}>Apply</Button>
      </form>

      {data?.avg_score != null && (
        <Card className="max-w-sm border-emerald-500/20 bg-emerald-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Window average</CardTitle>
          </CardHeader>
          <CardContent className={`text-2xl font-mono ${scoreColor(data.avg_score)}`}>
            {data.avg_score >= 0 ? "+" : ""}
            {data.avg_score.toFixed(3)}
          </CardContent>
        </Card>
      )}

      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !error && data && data.count === 0 && (
        <EmptyState message="No sentiment history on disk yet." />
      )}

      {data && data.rows.length > 0 && (
        <HoverCard>
          <CardContent className="overflow-x-auto p-0 pt-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.rows.map((row, i) => {
                  const s = row.sentiment_score;
                  return (
                    <TableRow key={i}>
                      <TableCell className="text-xs">{row.trade_date ?? "—"}</TableCell>
                      <TableCell className="font-mono">{row.symbol ?? "—"}</TableCell>
                      <TableCell>{row.platform ?? "—"}</TableCell>
                      <TableCell
                        className={`font-mono ${s != null ? scoreColor(Number(s)) : ""}`}
                      >
                        {s != null ? Number(s).toFixed(3) : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </HoverCard>
      )}

      {(data?.evidence_posts?.length ?? 0) > 0 && (
        <HoverCard className="mt-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">
              评论证据（近 {data?.lookback_days ?? 14} 日，已过滤广告/噪声）
            </CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日期</TableHead>
                  <TableHead>平台</TableHead>
                  <TableHead>摘要</TableHead>
                  <TableHead>分</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data!.evidence_posts!.map((row, i) => {
                  const s = row.ai_score;
                  return (
                    <TableRow key={i}>
                      <TableCell className="text-xs">{row.trade_date ?? "—"}</TableCell>
                      <TableCell>{row.platform ?? "—"}</TableCell>
                      <TableCell className="max-w-lg text-sm">
                        <p className="line-clamp-2">{row.title ?? "—"}</p>
                      </TableCell>
                      <TableCell
                        className={`font-mono text-xs ${s != null ? scoreColor(Number(s)) : ""}`}
                      >
                        {s != null ? Number(s).toFixed(3) : "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </HoverCard>
      )}
    </PageChrome>
  );
}
