"use client";
import { useEffect, useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Spinner, Alert } from "@/components/ui";
import { api, HealthResponse } from "@/lib/api";
import {
  FileSearch,
  Users,
  FileUp,
  Activity,
  CheckCircle2,
  XCircle,
  ArrowRight,
  TrendingUp,
  Cpu,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.health
      .get()
      .then(setHealth)
      .catch(() =>
        setHealth({ status: "unhealthy", checks: { database: "unreachable" } })
      )
      .finally(() => setLoading(false));
  }, []);

  const isHealthy = health?.status === "healthy";

  const quickLinks = [
    {
      title: "Submit Requisition",
      description: "Post a new job requirement and start AI matching",
      href: "/requisitions",
      icon: FileSearch,
      color: "text-indigo-600 bg-indigo-50",
    },
    {
      title: "Team Members",
      description: "Sync skill availability and team data",
      href: "/team-members",
      icon: Users,
      color: "text-violet-600 bg-violet-50",
    },
    {
      title: "Resume Ingestion",
      description: "Ingest resumes from Google Drive for vector matching",
      href: "/resumes",
      icon: FileUp,
      color: "text-teal-600 bg-teal-50",
    },
    {
      title: "System Health",
      description: "Monitor API status, DB and Prometheus metrics",
      href: "/system",
      icon: Activity,
      color: "text-orange-600 bg-orange-50",
    },
  ];

  return (
    <>
      <Topbar title="Dashboard" />
      <div className="p-6 space-y-6">
        {/* Hero */}
        <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 p-6 text-white shadow-lg">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold">IB Job Skill Mapping System</h2>
              <p className="mt-1 text-indigo-200 text-sm max-w-xl">
                AI-powered matching engine that pairs job descriptions with the best
                available team members using LangGraph, vector embeddings, and
                deterministic scoring.
              </p>
              <div className="mt-4 flex items-center gap-3">
                <Link
                  href="/requisitions"
                  className="flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 transition-colors shadow-sm"
                >
                  New Requisition <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
            <Cpu className="h-16 w-16 opacity-20" />
          </div>
        </div>

        {/* System status */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">API Status</p>
                {loading ? (
                  <Spinner className="mt-2 h-5 w-5" />
                ) : (
                  <div className="mt-1 flex items-center gap-2">
                    {isHealthy ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
                    )}
                    <span className={cn("text-sm font-semibold", isHealthy ? "text-emerald-700" : "text-red-700")}>
                      {isHealthy ? "Healthy" : "Unhealthy"}
                    </span>
                  </div>
                )}
              </div>
              <Activity className="h-8 w-8 text-slate-200" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Database</p>
                {loading ? (
                  <Spinner className="mt-2 h-5 w-5" />
                ) : (
                  <div className="mt-1 flex items-center gap-2">
                    {health?.checks?.database === "healthy" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
                    )}
                    <span className={cn("text-sm font-semibold", health?.checks?.database === "healthy" ? "text-emerald-700" : "text-red-700")}>
                      {health?.checks?.database === "healthy" ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">AI Pipeline</p>
                <div className="mt-1 flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-indigo-500" />
                  <span className="text-sm font-semibold text-indigo-700">LangGraph Active</span>
                </div>
              </div>
              <Cpu className="h-8 w-8 text-slate-200" />
            </div>
          </Card>
        </div>

        {/* Quick Links */}
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Quick Actions</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {quickLinks.map(({ title, description, href, icon: Icon, color }) => (
              <Link key={href} href={href}>
                <Card className="h-full p-5 cursor-pointer hover:shadow-md hover:border-indigo-200 transition-all group">
                  <div className={cn("mb-3 inline-flex rounded-lg p-2.5", color)}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <p className="text-sm font-semibold text-slate-900 group-hover:text-indigo-700 transition-colors">{title}</p>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">{description}</p>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        {/* Architecture overview */}
        <Card className="p-6">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">AI Matching Pipeline</h3>
          <div className="flex flex-wrap items-center gap-2">
            {[
              { label: "JD Parsing", color: "bg-blue-100 text-blue-700 border-blue-200" },
              { label: "→", color: "text-slate-400 border-transparent bg-transparent" },
              { label: "Skill Normalisation", color: "bg-violet-100 text-violet-700 border-violet-200" },
              { label: "→", color: "text-slate-400 border-transparent bg-transparent" },
              { label: "Availability Evaluation", color: "bg-teal-100 text-teal-700 border-teal-200" },
              { label: "→", color: "text-slate-400 border-transparent bg-transparent" },
              { label: "Matching & Scoring", color: "bg-indigo-100 text-indigo-700 border-indigo-200" },
              { label: "→", color: "text-slate-400 border-transparent bg-transparent" },
              { label: "Explanation Generation", color: "bg-amber-100 text-amber-700 border-amber-200" },
              { label: "→", color: "text-slate-400 border-transparent bg-transparent" },
              { label: "Result Aggregation", color: "bg-emerald-100 text-emerald-700 border-emerald-200" },
            ].map(({ label, color }, i) => (
              <span key={i} className={cn("rounded-full border px-3 py-1 text-xs font-medium", color)}>
                {label}
              </span>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Scoring formula: <strong>40% skill match</strong> + <strong>40% vector similarity</strong> + <strong>20% experience</strong>
          </p>
        </Card>

        {!loading && !isHealthy && (
          <Alert type="error">
            <strong>API Unavailable:</strong> The backend is not reachable. Make sure the
            Docker compose stack is running on <code>http://localhost:8001</code>.
          </Alert>
        )}
      </div>
    </>
  );
}

