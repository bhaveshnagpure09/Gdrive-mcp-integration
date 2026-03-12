"use client";
import { useEffect, useState, useCallback } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Badge, Alert, Spinner } from "@/components/ui";
import { api, HealthResponse } from "@/lib/api";
import { RefreshCw, Activity, Database, CheckCircle2, XCircle } from "lucide-react";

interface MetricLine {
  name: string;
  labels: Record<string, string>;
  value: string;
  help?: string;
  type?: string;
}

function parsePrometheus(raw: string): MetricLine[] {
  const lines = raw.split("\n");
  const result: MetricLine[] = [];
  let currentHelp: string | undefined;
  let currentType: string | undefined;

  for (const line of lines) {
    if (line.startsWith("# HELP")) {
      const parts = line.slice(7).split(" ");
      currentHelp = parts.slice(1).join(" ");
    } else if (line.startsWith("# TYPE")) {
      const parts = line.slice(7).split(" ");
      currentType = parts[1];
    } else if (line && !line.startsWith("#")) {
      const braceStart = line.indexOf("{");
      const braceEnd = line.lastIndexOf("}");
      const spaceIdx = line.lastIndexOf(" ");

      let name: string;
      const labels: Record<string, string> = {};
      let value: string;

      if (braceStart > -1 && braceEnd > -1) {
        name = line.slice(0, braceStart);
        const labelStr = line.slice(braceStart + 1, braceEnd);
        value = line.slice(braceEnd + 2);
        for (const pair of labelStr.split(",")) {
          const [k, v] = pair.split("=");
          if (k && v) labels[k.trim()] = v.replace(/"/g, "").trim();
        }
      } else {
        name = line.slice(0, spaceIdx);
        value = line.slice(spaceIdx + 1);
      }

      result.push({ name, labels, value, help: currentHelp, type: currentType });
    }
  }
  return result;
}

function MetricValue({ value }: { value: string }) {
  const num = parseFloat(value);
  const formatted = isNaN(num) ? value : num % 1 === 0 ? num.toLocaleString() : num.toFixed(4);
  return <span className="font-mono text-xs text-slate-800">{formatted}</span>;
}

export default function SystemPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [metricsRaw, setMetricsRaw] = useState<string>("");
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    setHealthLoading(true);
    setMetricsLoading(true);
    setHealthError(null);
    setMetricsError(null);

    await Promise.all([
      api.health
        .get()
        .then(setHealth)
        .catch((e) => setHealthError(e.message))
        .finally(() => setHealthLoading(false)),
      api.metrics
        .getRaw()
        .then(setMetricsRaw)
        .catch((e) => setMetricsError(e.message))
        .finally(() => setMetricsLoading(false)),
    ]);
    setLastRefresh(new Date());
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchAll();
  }, [fetchAll]);

  const metrics = metricsRaw ? parsePrometheus(metricsRaw) : [];

  // Group metrics by name prefix
  const grouped: Record<string, MetricLine[]> = {};
  for (const m of metrics) {
    const group = m.name.split("_").slice(0, 2).join("_");
    if (!grouped[group]) grouped[group] = [];
    grouped[group].push(m);
  }

  return (
    <>
      <Topbar title="System Health" />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-800">System Status</h2>
            <p className="text-xs text-slate-500">
              {lastRefresh
                ? `Last refreshed ${lastRefresh.toLocaleTimeString()}`
                : "Loading…"}
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={fetchAll} loading={healthLoading || metricsLoading}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>

        {/* Health Cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {/* API Status */}
          {healthLoading ? (
            <Card className="flex items-center gap-3 p-4">
              <Spinner className="h-4 w-4" />
              <span className="text-sm text-slate-500">Checking API…</span>
            </Card>
          ) : healthError ? (
            <Card className="border-red-200 bg-red-50 p-4 col-span-2 flex items-center gap-3">
              <XCircle className="h-5 w-5 text-red-500" />
              <span className="text-sm text-red-700">API unavailable: {healthError}</span>
            </Card>
          ) : health ? (
            <>
              <Card className="p-4 flex items-start gap-3">
                <div className={`mt-0.5 rounded-full p-1.5 ${health.status === "healthy" ? "bg-emerald-100" : "bg-red-100"}`}>
                  <Activity className={`h-4 w-4 ${health.status === "healthy" ? "text-emerald-600" : "text-red-600"}`} />
                </div>
                <div>
                  <p className="text-xs text-slate-500">API Status</p>
                  <p className="text-sm font-semibold text-slate-800 mt-0.5 capitalize">{health.status}</p>
                  <Badge variant={health.status === "healthy" ? "success" : "danger"} className="mt-1">
                    {health.status === "healthy" ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                    {health.status}
                  </Badge>
                </div>
              </Card>

              {health.checks &&
                Object.entries(health.checks).map(([key, val]) => (
                  <Card key={key} className="p-4 flex items-start gap-3">
                    <div className={`mt-0.5 rounded-full p-1.5 ${val === "healthy" ? "bg-emerald-100" : "bg-amber-100"}`}>
                      <Database className={`h-4 w-4 ${val === "healthy" ? "text-emerald-600" : "text-amber-600"}`} />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 capitalize">{key}</p>
                      <p className="text-sm font-semibold text-slate-800 mt-0.5 capitalize">{String(val)}</p>
                      <Badge variant={val === "healthy" ? "success" : "warning"} className="mt-1">
                        {String(val)}
                      </Badge>
                    </div>
                  </Card>
                ))}

            </>
          ) : null}
        </div>

        {/* Metrics */}
        <div>
          <h2 className="text-base font-semibold text-slate-800 mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4 text-violet-600" />
            Prometheus Metrics
          </h2>

          {metricsLoading ? (
            <Card className="flex items-center justify-center gap-3 py-16">
              <Spinner className="h-6 w-6" />
              <span className="text-sm text-slate-500">Loading metrics…</span>
            </Card>
          ) : metricsError ? (
            <Alert type="error">Failed to load metrics: {metricsError}</Alert>
          ) : metrics.length === 0 ? (
            <Alert type="warning">No metrics available.</Alert>
          ) : (
            <div className="space-y-4">
              {Object.entries(grouped).map(([group, items]) => (
                <Card key={group} className="overflow-hidden">
                  <div className="border-b border-slate-100 bg-slate-50 px-4 py-2 flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-violet-700">{group}_*</span>
                    <span className="text-xs text-slate-500">({items.length} series)</span>
                    {items[0]?.type && (
                      <Badge variant="info" className="ml-auto">{items[0].type}</Badge>
                    )}
                  </div>
                  {items[0]?.help && (
                    <div className="px-4 py-2 bg-slate-50/50 border-b border-slate-100 text-xs text-slate-500">
                      {items[0].help}
                    </div>
                  )}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100">
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-slate-500">Metric</th>
                          {Object.keys(items[0]?.labels || {}).map((k) => (
                            <th key={k} className="px-4 py-2.5 text-left text-xs font-medium text-slate-500 capitalize">
                              {k}
                            </th>
                          ))}
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-slate-500">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {items.map((m, i) => (
                          <tr key={i} className="hover:bg-slate-50 transition-colors">
                            <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{m.name}</td>
                            {Object.values(m.labels).map((v, vi) => (
                              <td key={vi} className="px-4 py-2.5 text-xs text-slate-500">
                                {v}
                              </td>
                            ))}
                            <td className="px-4 py-2.5 text-right">
                              <MetricValue value={m.value} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              ))}

              {/* Raw toggle */}
              <details className="group">
                <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600 transition-colors select-none">
                  View raw Prometheus text
                </summary>
                <Card className="mt-2">
                  <pre className="overflow-x-auto p-4 text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {metricsRaw}
                  </pre>
                </Card>
              </details>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
