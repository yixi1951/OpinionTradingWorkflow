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

type SentimentResponse = {
  ok: boolean;
  rows: SentimentRow[];
  count: number;
  avg_score: number | null;
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
      const q = new URLSearchParams({ limit: "80" });
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
      description="来自 sentiment_history.jsonl 的近期记录。"
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
    </PageChrome>
  );
}
