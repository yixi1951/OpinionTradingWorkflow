"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/data-states";
import { apiGet, API_BASE } from "@/lib/api";
import type { StatusResponse } from "@/lib/types";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

function healthBadge(status?: string) {
  if (status === "ok" || status === "ready") {
    return <Badge className="bg-emerald-600/20 text-emerald-400">healthy</Badge>;
  }
  if (status === "down") {
    return <Badge variant="destructive">down</Badge>;
  }
  return <Badge variant="secondary">{status ?? "unknown"}</Badge>;
}

export default function OverviewPage() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const st = await apiGet<StatusResponse>("/v1/status");
      setData(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const services = data
    ? [
        { name: "API gateway", key: "api" as const, raw: data.api },
        { name: "Collector", key: "collector" as const, raw: data.collector },
        { name: "Inference", key: "inference" as const, raw: data.inference },
        { name: "Compute", key: "compute" as const, raw: data.compute },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="text-sm text-muted-foreground">
            Live service health from <code className="text-xs">{API_BASE}</code>
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {loading && !data && <LoadingBlock />}
      {error && <ErrorState message={error} />}
      {!loading && !error && !data && (
        <EmptyState message="No status payload returned." />
      )}

      {data && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {services.map((svc) => {
            const status =
              svc.key === "api"
                ? svc.raw === "ok" ? "ok" : String(svc.raw)
                : (svc.raw as { status?: string })?.status;
            return (
              <Card key={svc.name} className="border-border/80 bg-card/80">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {svc.name}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center justify-between">
                  {healthBadge(status)}
                  {svc.key !== "api" && (svc.raw as { error?: string })?.error && (
                    <span className="max-w-[60%] truncate font-mono text-[10px] text-destructive">
                      {(svc.raw as { error?: string }).error}
                    </span>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
