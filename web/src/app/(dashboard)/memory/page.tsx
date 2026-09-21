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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";

type QueryResponse = {
  ok: boolean;
  rows: Record<string, unknown>[];
  count: number;
};

type RecallResponse = {
  ok: boolean;
  recall: Record<string, unknown>;
};

export default function MemoryPage() {
  const [kinds, setKinds] = useState<string[]>([]);
  const [kind, setKind] = useState("sentiment");
  const [symbol, setSymbol] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [recall, setRecall] = useState<Record<string, unknown> | null>(null);
  const [recallSymbol, setRecallSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet<{ kinds: string[] }>("/v1/memory/kinds")
      .then((r) => setKinds(r.kinds))
      .catch(() => setKinds(["sentiment", "signals", "trades", "events"]));
  }, []);

  const query = async () => {
    setLoading(true);
    setError(null);
    try {
      const q = new URLSearchParams({ kind, limit: "50" });
      if (symbol.trim()) q.set("symbol", symbol.trim());
      const res = await apiGet<QueryResponse>(`/v1/memory/query?${q}`);
      setRows(res.rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setLoading(false);
    }
  };

  const runRecall = async () => {
    if (!recallSymbol.trim()) return;
    setError(null);
    try {
      const res = await apiGet<RecallResponse>(
        `/v1/memory/recall?symbol=${encodeURIComponent(recallSymbol.trim())}`,
      );
      setRecall(res.recall);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Recall failed");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Historical memory</h1>
        <p className="text-sm text-muted-foreground">
          Filter JSONL stores (signals, sentiment, trades, events).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Query</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <div className="space-y-1">
            <Label>Kind</Label>
            <Select
              value={kind}
              onValueChange={(v) => {
                if (v) setKind(v);
              }}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {kinds.map((k) => (
                  <SelectItem key={k} value={k}>{k}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Symbol</Label>
            <Input
              className="w-36 font-mono"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="optional"
            />
          </div>
          <Button onClick={query} disabled={loading} className="self-end">
            Search
          </Button>
        </CardContent>
      </Card>

      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && rows.length === 0 && !error && (
        <EmptyState message="No rows — adjust filters or run the pipeline." />
      )}

      {rows.length > 0 && (
        <Card>
          <CardContent className="overflow-x-auto p-0 pt-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Summary</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs">
                      {String(row.trade_date ?? row.date ?? "—")}
                    </TableCell>
                    <TableCell className="font-mono">
                      {String(row.symbol ?? "—")}
                    </TableCell>
                    <TableCell className="max-w-xl truncate font-mono text-[10px] text-muted-foreground">
                      {JSON.stringify(row).slice(0, 120)}…
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Symbol recall (compact context)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Input
              className="w-40 font-mono"
              placeholder="600519"
              value={recallSymbol}
              onChange={(e) => setRecallSymbol(e.target.value)}
            />
            <Button type="button" variant="secondary" onClick={runRecall}>
              Recall
            </Button>
          </div>
          {recall && (
            <ScrollArea className="h-48 rounded-md border border-border bg-muted/20 p-3">
              <pre className="text-xs">{JSON.stringify(recall, null, 2)}</pre>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
