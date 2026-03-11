"use client";
import { useEffect, useState } from "react";
import { api, HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CheckCircle, XCircle, RefreshCw, Bell } from "lucide-react";

export default function Topbar({ title }: { title: string }) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    setChecking(true);
    try {
      const h = await api.health.get();
      setHealth(h);
    } catch {
      setHealth({ status: "unhealthy", checks: { database: "unreachable" } });
    }
    setChecking(false);
  };

  useEffect(() => {
    check();
    const t = setInterval(check, 30_000);
    return () => clearInterval(t);
  }, []);

  const isHealthy = health?.status === "healthy";

  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
      <div className="flex items-center gap-4">
        {/* API status pill */}
        <button
          onClick={check}
          title="Refresh API status"
          className={cn(
            "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            health === null
              ? "border-slate-200 text-slate-400"
              : isHealthy
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          )}
        >
          {checking ? (
            <RefreshCw className="h-3 w-3 animate-spin" />
          ) : isHealthy ? (
            <CheckCircle className="h-3 w-3" />
          ) : (
            <XCircle className="h-3 w-3" />
          )}
          {health === null ? "Checking…" : isHealthy ? "API Healthy" : "API Down"}
        </button>

        {/* Notifications placeholder */}
        <button className="relative rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
          <Bell className="h-4 w-4" />
        </button>

        {/* Avatar */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
          IB
        </div>
      </div>
    </header>
  );
}
