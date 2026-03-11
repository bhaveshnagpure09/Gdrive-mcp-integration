"use client";
import { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Input, Badge, Alert } from "@/components/ui";
import { api, IngestionResult } from "@/lib/api";
import { FileUp, HardDrive, RefreshCw, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export default function ResumesPage() {
  const [mode, setMode] = useState<"single" | "all">("single");
  const [docId, setDocId] = useState("");
  const [storageType, setStorageType] = useState("gdrive");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleIngest = async () => {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const payload =
        mode === "all"
          ? { storage: storageType, fetch_all: true }
          : { storage: storageType, doc_id: docId };
      const res = await api.resumes.ingest(payload);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Topbar title="Resume Ingestion" />
      <div className="p-6 space-y-5">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Ingest Resumes from Google Drive</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Trigger the AI pipeline to parse resumes, extract skills, and update the vector index.
          </p>
        </div>

        {/* Mode Switcher */}
        <Card>
          <div className="p-4 space-y-4">
            <div className="flex gap-2">
              <button
                onClick={() => setMode("single")}
                className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
                  mode === "single"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <FileUp className="h-4 w-4" />
                  Single Document
                </div>
                <p className="text-xs font-normal mt-1 opacity-70">Ingest one resume by Document ID</p>
              </button>
              <button
                onClick={() => setMode("all")}
                className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-all ${
                  mode === "all"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-center gap-2">
                  <HardDrive className="h-4 w-4" />
                  Fetch All
                </div>
                <p className="text-xs font-normal mt-1 opacity-70">Scan the entire drive folder</p>
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="block text-sm font-medium text-slate-700">Storage Type</label>
                <select
                  value={storageType}
                  onChange={(e) => setStorageType(e.target.value)}
                  className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                >
                  <option value="gdrive">Google Drive</option>
                </select>
              </div>
              {mode === "single" && (
                <Input
                  label="Document ID"
                  value={docId}
                  onChange={(e) => setDocId(e.target.value)}
                  placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
                />
              )}
            </div>

            <div className="bg-amber-50 rounded-lg border border-amber-200 p-3">
              <div className="flex gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <div className="text-xs text-amber-800">
                  {mode === "all" ? (
                    <span>
                      <strong>Batch ingestion</strong> will scan the entire configured Google Drive folder.
                      This may take several minutes depending on the number of files.
                    </span>
                  ) : (
                    <span>
                      Provide the <strong>Google Drive File ID</strong> from the document's share URL:
                      docs.google.com/document/d/<code className="bg-amber-100 px-1 rounded">FILE_ID</code>/edit
                    </span>
                  )}
                </div>
              </div>
            </div>

            <Button
              onClick={handleIngest}
              loading={loading}
              disabled={mode === "single" && !docId.trim()}
              className="w-full"
            >
              <RefreshCw className="h-4 w-4" />
              {loading ? "Ingesting…" : mode === "all" ? "Start Batch Ingestion" : "Ingest Resume"}
            </Button>
          </div>
        </Card>

        {error && <Alert type="error">{error}</Alert>}

        {/* Result */}
        {result && (
          <Card>
            <div className="border-b border-slate-100 px-5 py-3 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <h3 className="font-semibold text-sm text-slate-800">Ingestion Complete</h3>
            </div>
            <div className="p-5 space-y-4">
              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-center">
                  <p className="text-2xl font-bold text-emerald-700">{result.ingested}</p>
                  <p className="text-xs text-emerald-600 mt-1">Ingested</p>
                </div>
                <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-center">
                  <p className="text-2xl font-bold text-red-700">{result.failed}</p>
                  <p className="text-xs text-red-600 mt-1">Failed</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-center">
                  <p className="text-2xl font-bold text-slate-700">{result.ingested + result.failed}</p>
                  <p className="text-xs text-slate-600 mt-1">Total</p>
                </div>
              </div>

              {/* Details Table */}
              {result.details && result.details.length > 0 && (
                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Team Member ID</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Status</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {result.details.map((d, i) => (
                        <tr key={i} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-3 font-mono text-xs text-slate-700 max-w-[200px] truncate">
                            {d.team_member_id || <span className="text-slate-400">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            {d.status === "success" ? (
                              <Badge variant="success">
                                <CheckCircle2 className="h-3 w-3" /> Success
                              </Badge>
                            ) : (
                              <Badge variant="danger">
                                <XCircle className="h-3 w-3" /> Failed
                              </Badge>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500">
                            {d.error || <span className="text-slate-300">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
