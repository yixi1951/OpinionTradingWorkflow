"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiPost } from "@/lib/api";
import { ErrorState } from "@/components/data-states";
import { toast } from "sonner";

type RunDailyResponse = {
  collect: unknown;
  compute: unknown;
};

export default function RunDailyPage() {
  const [tradeDate, setTradeDate] = useState("");
  const [collect, setCollect] = useState(false);
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunDailyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const execute = async () => {
    setOpen(false);
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const body = {
        trade_date: tradeDate.trim() || null,
        collect,
        fast_daily: true,
        top_n: 5,
      };
      const res = await apiPost<RunDailyResponse>("/v1/run/daily", body);
      setResult(res);
      toast.success("Daily run finished");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Run failed";
      setError(msg);
      toast.error("Daily run failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Run daily pipeline</h1>
        <p className="text-sm text-muted-foreground">
          POST <code className="text-xs">/v1/run/daily</code> — optional collect + compute.
        </p>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle className="text-base">Parameters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="date">Trade date (optional)</Label>
            <Input
              id="date"
              placeholder="YYYY-MM-DD"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className="font-mono"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={collect}
              onChange={(e) => setCollect(e.target.checked)}
              className="rounded border-border"
            />
            Run collector first (slower; needs live crawl config)
          </label>
          <Button
            disabled={running}
            onClick={() => setOpen(true)}
            className="w-full sm:w-auto"
          >
            {running ? "Running…" : "Run daily"}
          </Button>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm daily run</DialogTitle>
            <DialogDescription>
              This triggers backend compute{collect ? " after collect" : ""}. It may take several
              minutes when LLM scoring is enabled.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={execute}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {error && <ErrorState message={error} />}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Response</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-96 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
              {JSON.stringify(result, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
