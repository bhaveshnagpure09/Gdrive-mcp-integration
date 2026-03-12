"use client";
import { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Input, Badge, Alert } from "@/components/ui";
import { api, IngestionResult } from "@/lib/api";
import { FileUp, HardDrive, FolderOpen, Globe, RefreshCw, CheckCircle2, XCircle, AlertTriangle, ExternalLink } from "lucide-react";

type ScopeType = "entire_drive" | "folder";

/** Strip a full Google Drive URL to its bare file/folder ID, or return input as-is. */
function extractGoogleId(raw: string): string {
  const folderMatch = raw.match(/\/folders\/([a-zA-Z0-9_-]{10,})/);
  if (folderMatch) return folderMatch[1];
  const docMatch = raw.match(/\/d\/([a-zA-Z0-9_-]{10,})/);
  if (docMatch) return docMatch[1];
  return raw.trim();
}

export default function ResumesPage() {
  const [mode, setMode] = useState<"single" | "all">("single");
  const [docId, setDocId] = useState("");
  const [storageType, setStorageType] = useState("gdrive");
  const [scope, setScope] = useState<ScopeType>("entire_drive");
  const [folderId, setFolderId] = useState("");
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
          ? {
              storage: storageType,
              fetch_all: true,
              ...(scope === "folder" && folderId.trim()
                ? { folder_id: extractGoogleId(folderId) }
                : {}),
            }
          : { storage: storageType, doc_id: extractGoogleId(docId) };
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
                <div className="space-y-2">
                  {/* Step 1 hint — open Drive and grab the URL */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-semibold text-slate-700">Resume Document</label>
                    <a
                      href="https://drive.google.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 hover:underline transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19 4H5a2 2 0 00-2 2v12a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2zm-7 10l-4-4h3V7h2v3h3l-4 4z" />
                      </svg>
                      Open Google Drive ↗
                    </a>
                  </div>
                  <Input
                    label=""
                    value={docId}
                    onChange={(e) => setDocId(e.target.value)}
                    placeholder="Paste candidate doc URL or ID — e.g. https://drive.google.com/file/d/..."
                  />
                  <p className="text-xs text-slate-400">
                    In Google Drive, right-click a résumé file → <strong>Share → Copy link</strong>, then paste it above.
                    Full URLs and bare IDs are both accepted.
                  </p>
                  {docId.trim() && (
                    <div className="flex items-center gap-2 rounded-lg bg-indigo-50 border border-indigo-200 px-3 py-2">
                      <span className="text-xs text-indigo-500 font-medium">Detected ID:</span>
                      <code className="text-xs font-mono text-indigo-700 truncate flex-1">{extractGoogleId(docId)}</code>
                      {docId.startsWith("http") && (
                        <a
                          href={docId}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-auto flex-shrink-0 text-xs text-indigo-600 hover:underline inline-flex items-center gap-0.5"
                        >
                          Preview <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── Scope selector (Fetch All + gdrive only) ── */}
            {mode === "all" && storageType === "gdrive" && (
              <div className="space-y-3">
                <label className="block text-sm font-semibold text-slate-700">Source Location</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setScope("entire_drive")}
                    className={`flex items-start gap-3 rounded-xl border p-3.5 text-left transition-all ${
                      scope === "entire_drive"
                        ? "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <Globe className={`mt-0.5 h-4 w-4 shrink-0 ${ scope === "entire_drive" ? "text-indigo-600" : "text-slate-400" }`} />
                    <div>
                      <p className={`text-sm font-semibold ${ scope === "entire_drive" ? "text-indigo-700" : "text-slate-700" }`}>
                        Entire Drive
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">Scan all Google Docs across your Drive</p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setScope("folder")}
                    className={`flex items-start gap-3 rounded-xl border p-3.5 text-left transition-all ${
                      scope === "folder"
                        ? "border-indigo-500 bg-indigo-50 ring-1 ring-indigo-400"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <FolderOpen className={`mt-0.5 h-4 w-4 shrink-0 ${ scope === "folder" ? "text-indigo-600" : "text-slate-400" }`} />
                    <div>
                      <p className={`text-sm font-semibold ${ scope === "folder" ? "text-indigo-700" : "text-slate-700" }`}>
                        Specific Folder
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">Ingest only from a chosen Drive folder</p>
                    </div>
                  </button>
                </div>

                {scope === "folder" && (
                  <div className="space-y-1.5">
                    <Input
                      label="Google Drive Folder ID or URL"
                      value={folderId}
                      onChange={(e) => setFolderId(e.target.value)}
                      placeholder="https://drive.google.com/drive/folders/... or bare ID"
                    />
                    {folderId && folderId.startsWith("http") && (
                      <p className="text-xs text-indigo-600">
                        Detected ID: <code className="bg-indigo-50 rounded px-1 font-mono">{extractGoogleId(folderId)}</code>
                      </p>
                    )}
                    <p className="text-xs text-slate-400">
                      Paste the full folder URL or just the ID from{" "}
                      <span className="font-mono bg-slate-100 rounded px-1">drive.google.com/drive/folders/<strong>FOLDER_ID</strong></span>
                      {" · "}
                      <a
                        href="https://drive.google.com"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-0.5 text-indigo-600 hover:underline"
                      >
                        Open Drive <ExternalLink className="h-3 w-3" />
                      </a>
                    </p>
                  </div>
                )}
              </div>
            )}

            <div className="bg-amber-50 rounded-lg border border-amber-200 p-3">
              <div className="flex gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <div className="text-xs text-amber-800">
                  {mode === "all" ? (
                    scope === "folder" && folderId.trim() ? (
                      <span>
                        <strong>Folder ingestion</strong> will scan only the specified Drive folder.
                        Ensure the folder is shared with the authenticated service account.
                      </span>
                    ) : (
                      <span>
                        <strong>Batch ingestion</strong> will scan the entire Google Drive.
                        This may take several minutes depending on the number of files.
                      </span>
                    )
                  ) : (
                    <span>
                      Provide the <strong>Google Drive File ID</strong> from the document&apos;s share URL:
                      docs.google.com/document/d/<code className="bg-amber-100 px-1 rounded">FILE_ID</code>/edit
                    </span>
                  )}
                </div>
              </div>
            </div>

            <Button
              onClick={handleIngest}
              loading={loading}
              disabled={mode === "single" && !docId.trim() || (mode === "all" && scope === "folder" && !folderId.trim())}
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
              <div className="grid grid-cols-4 gap-3">
                <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-center">
                  <p className="text-2xl font-bold text-emerald-700">{result.ingested}</p>
                  <p className="text-xs text-emerald-600 mt-1">Ingested</p>
                </div>
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-center">
                  <p className="text-2xl font-bold text-amber-700">{result.skipped ?? 0}</p>
                  <p className="text-xs text-amber-600 mt-1">Already Ingested</p>
                </div>
                <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-center">
                  <p className="text-2xl font-bold text-red-700">{result.failed}</p>
                  <p className="text-xs text-red-600 mt-1">Failed</p>
                </div>
                <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-center">
                  <p className="text-2xl font-bold text-slate-700">{result.ingested + (result.skipped ?? 0) + result.failed}</p>
                  <p className="text-xs text-slate-600 mt-1">Total</p>
                </div>
              </div>

              {/* Details Table */}
              {result.details && result.details.length > 0 && (
                <div className="rounded-lg border border-slate-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">#</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">File Name</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Status</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Extracted Name</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Skills Found</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Exp (mo)</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-slate-600">Error / Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {result.details.map((d, i) => (
                        <tr
                          key={i}
                          className={
                            d.status === "failed"
                              ? "bg-red-50 hover:bg-red-50"
                              : d.status === "already_ingested"
                              ? "bg-amber-50 hover:bg-amber-50"
                              : "hover:bg-slate-50"
                          }
                        >
                          <td className="px-4 py-2.5 text-xs text-slate-400">{i + 1}</td>
                          <td className="px-4 py-2.5 text-xs text-slate-700 font-medium max-w-[180px] truncate" title={d.file_name || d.doc_id}>
                            {d.file_name || d.doc_id || <span className="text-slate-400">—</span>}
                          </td>
                          <td className="px-4 py-2.5">
                            {d.status === "ok" ? (
                              <Badge variant="success">
                                <CheckCircle2 className="h-3 w-3" /> New
                              </Badge>
                            ) : d.status === "updated" ? (
                              <Badge variant="warning">
                                <CheckCircle2 className="h-3 w-3" /> Updated
                              </Badge>
                            ) : d.status === "already_ingested" ? (
                              <Badge variant="default">
                                <span className="h-3 w-3 text-amber-600">↩</span> Skipped
                              </Badge>
                            ) : (
                              <Badge variant="danger">
                                <XCircle className="h-3 w-3" /> Failed
                              </Badge>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-600">
                            {d.extracted_name || <span className="text-slate-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-600">
                            {d.skills_found != null ? (
                              <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-emerald-700 font-semibold">
                                {d.skills_found}
                              </span>
                            ) : <span className="text-slate-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-slate-600">
                            {d.experience_months != null ? d.experience_months : <span className="text-slate-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-red-500 max-w-[200px] truncate" title={d.reason || d.error || ""}>
                            {d.reason || d.error || <span className="text-slate-300">—</span>}
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
