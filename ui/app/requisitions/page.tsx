"use client";
import { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Input, Textarea, Select, Badge, Alert, ScoreBar, Spinner } from "@/components/ui";
import { api, RequisitionRequest, MatchesResponse } from "@/lib/api";
import { cn, fitLevelColor, priorityColor, generateId } from "@/lib/utils";
import { Plus, X, Search, RefreshCw, CheckCircle2, Clock, AlertCircle } from "lucide-react";

const EMPTY_FORM = {
  clientName: "",
  title: "",
  role: "",
  priority: "HIGH" as const,
  jdText: "",
  mandatorySkills: [] as string[],
  preferredSkills: [] as string[],
  location: [] as string[],
  workMode: [] as string[],
  durationMonths: "",
  minExpMonths: "",
  maxExpMonths: "",
  department: "",
  submittedBy: "",
};

export default function RequisitionsPage() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [skillInput, setSkillInput] = useState("");
  const [prefSkillInput, setPrefSkillInput] = useState("");
  const [locationInput, setLocationInput] = useState("");
  const [workModeInput, setWorkModeInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchesResponse | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"form" | "results">("form");

  const set = (k: keyof typeof form, v: unknown) =>
    setForm((f) => ({ ...f, [k]: v }));

  const addTag = (
    key: "mandatorySkills" | "preferredSkills" | "location" | "workMode",
    value: string,
    setter: (v: string) => void
  ) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    set(key, [...(form[key] as string[]), trimmed]);
    setter("");
  };

  const removeTag = (
    key: "mandatorySkills" | "preferredSkills" | "location" | "workMode",
    idx: number
  ) => set(key, (form[key] as string[]).filter((_, i) => i !== idx));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const reqId = generateId();
      const payload: RequisitionRequest = {
        request_id: reqId,
        schema_version: "1.0",
        source_system: "ib-skill-mapper-ui",
        client_name: form.clientName,
        job_description: {
          client_name: form.clientName,
          title: form.title,
          role: form.role,
          priority: form.priority,
          location: form.location.length ? form.location : ["Remote"],
          work_mode: form.workMode.length ? form.workMode : ["Remote"],
          jd_text: form.jdText,
          mandatory_skills: form.mandatorySkills,
          preferred_skills: form.preferredSkills,
          ...(form.durationMonths && { requisition_duration_month: Number(form.durationMonths) }),
          ...(form.minExpMonths || form.maxExpMonths
            ? {
                experience: {
                  min_months: form.minExpMonths ? Number(form.minExpMonths) : undefined,
                  max_months: form.maxExpMonths ? Number(form.maxExpMonths) : undefined,
                },
              }
            : {}),
        },
        metadata: {
          submitted_by: form.submittedBy || "UI User",
          submitted_at: new Date().toISOString(),
          department: form.department || undefined,
        },
      };
      const res = await api.requisitions.create(payload);
      setCorrelationId(res.correlation_id);
      setTab("results");
      startPolling(res.correlation_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit requisition");
    } finally {
      setSubmitting(false);
    }
  };

  const startPolling = async (corrId: string) => {
    setPolling(true);
    let attempts = 0;
    const maxAttempts = 30;

    const poll = async () => {
      try {
        const res = await api.requisitions.getMatches(corrId);
        setMatches(res);
        if (res.status === "COMPLETED" || attempts >= maxAttempts) {
          setPolling(false);
          return;
        }
      } catch {
        // ignore polling errors
      }
      attempts++;
      if (attempts < maxAttempts) setTimeout(poll, 3000);
      else setPolling(false);
    };

    poll();
  };

  const refreshMatches = () => {
    if (correlationId) {
      setPolling(true);
      startPolling(correlationId);
    }
  };

  const TagInput = ({
    tags,
    inputValue,
    onInputChange,
    onAdd,
    onRemove,
    placeholder,
  }: {
    tags: string[];
    inputValue: string;
    onInputChange: (v: string) => void;
    onAdd: () => void;
    onRemove: (i: number) => void;
    placeholder: string;
  }) => (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), onAdd())}
          placeholder={placeholder}
        />
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((t, i) => (
            <span
              key={i}
              className="flex items-center gap-1 rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-xs font-medium text-indigo-700"
            >
              {t}
              <button type="button" onClick={() => onRemove(i)} className="hover:text-red-600">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <>
      <Topbar title="Requisitions" />
      <div className="p-6 space-y-5">
        {/* Tabs */}
        <div className="flex border-b border-slate-200">
          {(["form", "results"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "px-5 py-2.5 text-sm font-medium border-b-2 transition-colors",
                tab === t
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              )}
            >
              {t === "form" ? "Submit Requisition" : "Match Results"}
              {t === "results" && matches && (
                <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700">
                  {matches.total_matches}
                </span>
              )}
            </button>
          ))}
        </div>

        {error && <Alert type="error">{error}</Alert>}

        {/* ── FORM ── */}
        {tab === "form" && (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <Card className="lg:col-span-2 p-6 space-y-4">
                <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Job Details</h3>
                <div className="grid grid-cols-2 gap-4">
                  <Input label="Client Name *" required value={form.clientName} onChange={(e) => set("clientName", e.target.value)} placeholder="Acme Corp" />
                  <Input label="Job Title *" required value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Senior React Developer" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Input label="Role *" required value={form.role} onChange={(e) => set("role", e.target.value)} placeholder="Frontend Engineer" />
                  <Select label="Priority *" required value={form.priority} onChange={(e) => set("priority", e.target.value as typeof form.priority)}>
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </Select>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <Input label="Duration (months)" type="number" min="1" value={form.durationMonths} onChange={(e) => set("durationMonths", e.target.value)} placeholder="6" />
                  <Input label="Min Experience (months)" type="number" min="0" value={form.minExpMonths} onChange={(e) => set("minExpMonths", e.target.value)} placeholder="24" />
                  <Input label="Max Experience (months)" type="number" min="0" value={form.maxExpMonths} onChange={(e) => set("maxExpMonths", e.target.value)} placeholder="84" />
                </div>
                <Textarea
                  label="Job Description Text *"
                  required
                  rows={8}
                  value={form.jdText}
                  onChange={(e) => set("jdText", e.target.value)}
                  placeholder="Paste the full job description here..."
                />
              </Card>

              <div className="space-y-5">
                <Card className="p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Skills</h3>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">Mandatory Skills</label>
                    <TagInput
                      tags={form.mandatorySkills}
                      inputValue={skillInput}
                      onInputChange={setSkillInput}
                      onAdd={() => addTag("mandatorySkills", skillInput, setSkillInput)}
                      onRemove={(i) => removeTag("mandatorySkills", i)}
                      placeholder="e.g. React"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">Preferred Skills</label>
                    <TagInput
                      tags={form.preferredSkills}
                      inputValue={prefSkillInput}
                      onInputChange={setPrefSkillInput}
                      onAdd={() => addTag("preferredSkills", prefSkillInput, setPrefSkillInput)}
                      onRemove={(i) => removeTag("preferredSkills", i)}
                      placeholder="e.g. TypeScript"
                    />
                  </div>
                </Card>

                <Card className="p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Location & Work</h3>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">Locations</label>
                    <TagInput
                      tags={form.location}
                      inputValue={locationInput}
                      onInputChange={setLocationInput}
                      onAdd={() => addTag("location", locationInput, setLocationInput)}
                      onRemove={(i) => removeTag("location", i)}
                      placeholder="e.g. Mumbai"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">Work Mode</label>
                    <TagInput
                      tags={form.workMode}
                      inputValue={workModeInput}
                      onInputChange={setWorkModeInput}
                      onAdd={() => addTag("workMode", workModeInput, setWorkModeInput)}
                      onRemove={(i) => removeTag("workMode", i)}
                      placeholder="Remote / Hybrid / Onsite"
                    />
                  </div>
                </Card>

                <Card className="p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Metadata</h3>
                  <Input label="Submitted By" value={form.submittedBy} onChange={(e) => set("submittedBy", e.target.value)} placeholder="Your name" />
                  <Input label="Department" value={form.department} onChange={(e) => set("department", e.target.value)} placeholder="Engineering" />
                </Card>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setForm(EMPTY_FORM)}>Reset</Button>
              <Button type="submit" loading={submitting} className="min-w-[160px]">
                <Search className="h-4 w-4" /> Submit & Match
              </Button>
            </div>
          </form>
        )}

        {/* ── RESULTS ── */}
        {tab === "results" && (
          <div className="space-y-4">
            {correlationId && (
              <Card className="p-4">
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    {polling ? (
                      <Clock className="h-5 w-5 text-amber-500" />
                    ) : matches?.status === "COMPLETED" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-slate-400" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-slate-800">
                        Correlation ID: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{correlationId}</code>
                      </p>
                      <p className="text-xs text-slate-500">
                        Status: <strong>{polling ? "Processing…" : matches?.status ?? "QUEUED"}</strong>
                        {matches && ` · ${matches.total_matches} candidate(s) found`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {polling && <Spinner className="h-4 w-4" />}
                    <Button variant="outline" size="sm" onClick={refreshMatches}>
                      <RefreshCw className="h-3.5 w-3.5" /> Refresh
                    </Button>
                  </div>
                </div>
              </Card>
            )}

            {!correlationId && (
              <Alert type="info">
                Submit a requisition on the <strong>Submit Requisition</strong> tab to see match results here.
              </Alert>
            )}

            {matches?.matches && matches.matches.length > 0 ? (
              <div className="space-y-3">
                {matches.matches.map((m, idx) => (
                  <Card key={m.team_member_id} className="p-5">
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-700">
                          #{idx + 1}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{m.team_member_id}</p>
                          <div className="mt-0.5 flex items-center gap-2 flex-wrap">
                            <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-medium", fitLevelColor(m.fit_level))}>
                              {m.fit_level} FIT
                            </span>
                            <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-medium", m.availability_match ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200")}>
                              {m.availability_match ? "Available" : "Unavailable"}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="min-w-[180px]">
                        <p className="mb-1 text-xs text-slate-500">
                          Match Score: <strong className="text-slate-800">{(m.match_percentage ?? m.profile_score * 100).toFixed(1)}%</strong>
                        </p>
                        <ScoreBar value={m.match_percentage ?? m.profile_score * 100} />
                      </div>
                    </div>

                    {m.explanation.length > 0 && (
                      <div className="mt-4 rounded-lg bg-slate-50 p-3">
                        <p className="mb-1.5 text-xs font-medium text-slate-600">Explanation</p>
                        <ul className="space-y-1">
                          {m.explanation.map((line, i) => (
                            <li key={i} className="text-xs text-slate-700 flex gap-2">
                              <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                              {line}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            ) : (
              correlationId && !polling && matches?.status === "PROCESSING" && (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                  <Spinner className="h-8 w-8 mb-3" />
                  <p className="text-sm">AI pipeline is running…</p>
                  <p className="text-xs mt-1">This usually takes 15-30 seconds</p>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </>
  );
}
