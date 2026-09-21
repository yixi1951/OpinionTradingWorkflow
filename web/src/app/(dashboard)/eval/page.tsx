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
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet } from "@/lib/api";
import type { WalkForwardReport } from "@/lib/types";

type WfResponse = {
  ok: boolean;
  message?: string;
  report?: WalkForwardReport;
  report_dir?: string;
};

type MonthlyResponse = {
  ok: boolean;
  summary: Record<string, unknown>;
  rows: Record<string, unknown>[];
};

function pct(v: unknown) {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export default function EvalPage() {
  const [wf, setWf] = useState<WfResponse | null>(null);
  const [monthly, setMonthly] = useState<MonthlyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [w, m] = await Promise.all([
          apiGet<WfResponse>("/v1/eval/walk-forward"),
          apiGet<MonthlyResponse>("/v1/eval/monthly"),
        ]);
        setWf(w);
        setMonthly(m);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load eval data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const report = wf?.report;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Eval &amp; walk-forward</h1>
        <p className="text-sm text-muted-foreground">
          Reads cached reports under <code className="text-xs">data/reports</code>.
        </p>
      </div>

      {loading && <LoadingBlock />}
      {error && <ErrorState message={error} />}

      {!loading && wf && !wf.ok && (
        <EmptyState
          message={
            wf.message ??
            "No walk_forward_report.json — run `python -m opinion_trading.main --mode walk_forward`."
          }
        />
      )}

      {report && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground">Avg test accuracy</CardTitle>
              </CardHeader>
              <CardContent className="text-xl font-mono">
                {pct(report.avg_test_accuracy)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground">Train→test gap</CardTitle>
              </CardHeader>
              <CardContent className="text-xl font-mono">
                {pct(report.avg_degradation_accuracy)}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-muted-foreground">Recommendation</CardTitle>
              </CardHeader>
              <CardContent className="text-sm">{report.recommendation ?? "—"}</CardContent>
            </Card>
          </div>

          {report.folds && report.folds.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Folds</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Test window</TableHead>
                      <TableHead>Train acc</TableHead>
                      <TableHead>Test acc</TableHead>
                      <TableHead>Degradation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.folds.map((f, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-xs font-mono">
                          {String(f.test_start)} → {String(f.test_end)}
                        </TableCell>
                        <TableCell>{pct(f.train_accuracy)}</TableCell>
                        <TableCell>{pct(f.test_accuracy)}</TableCell>
                        <TableCell>{pct(f.degradation_accuracy)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {monthly && monthly.ok && monthly.rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Latest monthly training</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  {Object.keys(monthly.rows[0]).slice(0, 6).map((k) => (
                    <TableHead key={k}>{k}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {monthly.rows.slice(0, 12).map((row, i) => (
                  <TableRow key={i}>
                    {Object.keys(monthly.rows[0]).slice(0, 6).map((k) => (
                      <TableCell key={k} className="text-xs">
                        {String(row[k] ?? "")}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
