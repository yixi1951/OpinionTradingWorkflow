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
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";
import type { PicksResponse, PickRow } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { PageChrome } from "@/components/page-chrome";
import { HoverCard } from "@/components/hover-card";
import { StockQuoteInline, StockSymbolCell } from "@/components/stock-symbol";

export default function PicksPage() {
  const [data, setData] = useState<PicksResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<PicksResponse>("/v1/picks?top_n=10");
        setData(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load picks");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const picks: PickRow[] = data?.picks ?? (Array.isArray(data) ? data : []);

  return (
    <PageChrome
      title="选股"
      description="最新排名信号（compute 服务；离线时可读 report CSV）。"
    >
      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {data?.error && <ErrorState message={String(data.error)} />}
      {!loading && !error && picks.length === 0 && (
        <EmptyState message="No picks yet — run the daily pipeline or check compute logs." />
      )}
      {picks.length > 0 && (
        <HoverCard>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Top rankings</CardTitle>
            {data?.trade_date && (
              <Badge variant="outline">{String(data.trade_date)}</Badge>
            )}
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>标的</TableHead>
                  <TableHead className="text-right">行情</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead className="min-w-[240px]">Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {picks.map((row, idx) => (
                  <TableRow key={`${row.symbol}-${idx}`}>
                    <TableCell>{row.rank ?? idx + 1}</TableCell>
                    <TableCell>
                      <StockSymbolCell symbol={row.symbol} name={row.name} />
                    </TableCell>
                    <TableCell>
                      <StockQuoteInline quote={row.quote} />
                    </TableCell>
                    <TableCell>
                      {row.score != null ? Number(row.score).toFixed(3) : "—"}
                    </TableCell>
                    <TableCell>{row.action ?? "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {row.reason ?? row.explanation ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </HoverCard>
      )}
    </PageChrome>
  );
}
