"use client";
import { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card, Button, Input, Textarea, Select, Alert, ScoreBar, Spinner } from "@/components/ui";
import { api, RequisitionRequest, MatchesResponse } from "@/lib/api";
import { cn, fitLevelColor, generateId } from "@/lib/utils";
import { Plus, X, Search, RefreshCw, CheckCircle2, Clock, AlertCircle, FileText, ExternalLink, Copy } from "lucide-react";

// ---------------------------------------------------------------------------
// TagInput defined at module level so its identity is stable across renders.
// Defining it inside the page component causes React to unmount+remount the
// <input> on every keystroke (component reference changes each render),
// which breaks focus and makes typing feel letter-by-letter.
// ---------------------------------------------------------------------------
function TagInput({
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
}) {
  return (
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
}

const EMPTY_FORM = {
  clientName: "",
  title: "",
  priority: "HIGH" as const,
  jdText: "",
  mandatorySkills: [] as string[],
  preferredSkills: [] as string[],
  location: [] as string[],
  workMode: [] as string[],
  durationMonths: "",
  minExpYears: "",
  maxExpYears: "",
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
    // Support comma/semicolon-separated bulk input: "Python, Django, REST"
    const items = value.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
    if (!items.length) return;
    set(key, [...(form[key] as string[]), ...items]);
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
      const minExpMonths = form.minExpYears ? Math.round(Number(form.minExpYears) * 12) : undefined;
      const maxExpMonths = form.maxExpYears ? Math.round(Number(form.maxExpYears) * 12) : undefined;

      const payload: RequisitionRequest = {
        request_id: reqId,
        schema_version: "1.0",
        source_system: "ib-skill-mapper-ui",
        client_name: form.clientName,
        job_description: {
          client_name: form.clientName,
          title: form.title,
          role: form.title,
          priority: form.priority,
          location: form.location.length ? form.location : ["Remote"],
          work_mode: form.workMode.length ? form.workMode : ["Remote"],
          jd_text: form.jdText,
          mandatory_skills: form.mandatorySkills,
          preferred_skills: form.preferredSkills,
          ...(form.durationMonths && { requisition_duration_month: Number(form.durationMonths) }),
          ...(minExpMonths !== undefined || maxExpMonths !== undefined
            ? { experience: { min_months: minExpMonths, max_months: maxExpMonths } }
            : {}),
        },
        metadata: {
          submitted_by: "UI User",
          submitted_at: new Date().toISOString(),
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
        if (res.status === "COMPLETED" || res.status === "NO_MATCH" || attempts >= maxAttempts) {
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

  // TagInput is defined at module level above — see top of file

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

              {/* Left: Job Details */}
              <Card className="lg:col-span-2 p-6 space-y-5">
                <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Job Details</h3>

                <div className="grid grid-cols-2 gap-4">
                  <Input
                    label="Client Name *"
                    required
                    value={form.clientName}
                    onChange={(e) => set("clientName", e.target.value)}
                    placeholder="e.g. InfoBeans"
                  />
                  <Input
                    label="Job Title *"
                    required
                    value={form.title}
                    onChange={(e) => set("title", e.target.value)}
                    placeholder="e.g. Senior QA Engineer"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <Select
                    label="Priority *"
                    required
                    value={form.priority}
                    onChange={(e) => set("priority", e.target.value as typeof form.priority)}
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                  </Select>
                  <Input
                    label="Project Duration (months)"
                    type="number"
                    min="1"
                    value={form.durationMonths}
                    onChange={(e) => set("durationMonths", e.target.value)}
                    placeholder="e.g. 6"
                  />
                  <div className="space-y-1">
                    <label className="block text-xs font-medium text-slate-700">Experience (years)</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={form.minExpYears}
                        onChange={(e) => set("minExpYears", e.target.value)}
                        placeholder="Min"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                      />
                      <span className="text-xs text-slate-400 shrink-0">to</span>
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={form.maxExpYears}
                        onChange={(e) => set("maxExpYears", e.target.value)}
                        placeholder="Max"
                        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                      />
                    </div>
                  </div>
                </div>

                <Textarea
                  label="Job Description *"
                  required
                  rows={9}
                  value={form.jdText}
                  onChange={(e) => set("jdText", e.target.value)}
                  placeholder="Paste the full job description here…"
                />
              </Card>

              {/* Right sidebar */}
              <div className="space-y-5">
                <Card className="p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Skills</h3>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">
                      Mandatory Skills
                    </label>
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
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">
                      Preferred Skills
                    </label>
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
                  <h3 className="text-sm font-semibold text-slate-700 border-b pb-2">Location & Work Mode</h3>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-700">Location</label>
                    <TagInput
                      tags={form.location}
                      inputValue={locationInput}
                      onInputChange={setLocationInput}
                      onAdd={() => addTag("location", locationInput, setLocationInput)}
                      onRemove={(i) => removeTag("location", i)}
                      placeholder="e.g. Pune"
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
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setForm(EMPTY_FORM)}>
                Reset
              </Button>
              <Button type="submit" loading={submitting} className="min-w-[160px]">
                <Search className="h-4 w-4" /> Submit &amp; Match
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
                    ) : matches?.status === "NO_MATCH" ? (
                      <AlertCircle className="h-5 w-5 text-amber-400" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-slate-400" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-slate-800">
                        Correlation ID:{" "}
                        <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                          {correlationId}
                        </code>
                      </p>
                      <p className="text-xs text-slate-500">
                        Status:{" "}
                        <strong>{polling ? "Processing…" : (matches?.status ?? "QUEUED")}</strong>
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
                Submit a requisition on the <strong>Submit Requisition</strong> tab to see match
                results here.
              </Alert>
            )}

            {matches?.matches && matches.matches.length > 0 ? (
              <div className="space-y-5">
                {matches.matches.map((m, idx) => {
                  const matchPct = m.match_percentage ?? m.profile_score * 100;
                  const skillPct = (m.skill_score ?? 0) * 100;
                  const expPct = (m.experience_score ?? 0) * 100;
                  const availPct = (m.availability_score ?? (m.availability_match ? 1 : 0)) * 100;
                  const displayName = m.full_name || m.team_member_id;

                  // Generate initials for avatar
                  const initials = displayName
                    .split(" ")
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((w: string) => w[0].toUpperCase())
                    .join("") || `#${idx + 1}`;

                  // Google Doc ID and resume href
                  const googleDocId = m.profile_url && !m.profile_url.startsWith("http")
                    ? m.profile_url
                    : null;
                  const resumeHref = m.profile_url
                    ? m.profile_url.startsWith("http")
                      ? m.profile_url
                      : `https://docs.google.com/document/d/${m.profile_url}`
                    : null;

                  const fitColors = {
                    bar: m.fit_level === "HIGH" ? "bg-emerald-500" : m.fit_level === "MEDIUM" ? "bg-amber-400" : "bg-rose-400",
                    avatar: m.fit_level === "HIGH" ? "bg-emerald-500 text-white" : m.fit_level === "MEDIUM" ? "bg-amber-400 text-white" : "bg-rose-400 text-white",
                  };

                  return (
                    <Card key={m.team_member_id} className="overflow-hidden border border-slate-200 shadow-sm">

                      {/* ── Fit-level top stripe ── */}
                      <div className={cn("h-1 w-full", fitColors.bar)} />

                      <div className="p-6 space-y-5">

                        {/* ── Section 1: Candidate Header ── */}
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                          <div className="flex items-start gap-4">
                            {/* Avatar */}
                            <div className={cn(
                              "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-sm font-bold shadow-sm",
                              fitColors.avatar
                            )}>
                              {initials}
                            </div>

                            <div className="space-y-1 min-w-0">
                              {/* Name + Fit badge */}
                              <div className="flex items-center gap-2.5 flex-wrap">
                                <h3 className="text-base font-bold text-slate-900 leading-tight">{displayName}</h3>
                                <span className={cn(
                                  "rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                                  fitLevelColor(m.fit_level)
                                )}>
                                  {m.fit_level} FIT
                                </span>
                              </div>

                              {/* Candidate ID */}
                              <p className="text-xs text-slate-400">
                                Candidate ID:{" "}
                                <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-600">
                                  {m.team_member_id}
                                </code>
                              </p>

                              {/* Google Doc ID + Resume link */}
                              {m.profile_url && (
                                <div className="flex items-center gap-2 flex-wrap mt-1.5">
                                  <FileText className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                  <span className="text-xs text-slate-400">Resume:</span>
                                  {googleDocId && (
                                    <span className="font-mono text-xs text-slate-500 bg-slate-100 rounded px-1.5 py-0.5 truncate max-w-[200px]"
                                      title={googleDocId}>
                                      {googleDocId}
                                    </span>
                                  )}
                                  <a
                                    href={resumeHref!}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 active:scale-95 transition-all"
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                    Open Resume
                                  </a>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Rank badge */}
                          <div className="flex shrink-0 items-center gap-1 rounded-full bg-slate-100 px-3 py-1.5">
                            <span className="text-sm font-bold text-slate-600">#{idx + 1}</span>
                            <span className="text-xs text-slate-400">/ {matches.matches.length}</span>
                          </div>
                        </div>

                        {/* ── Section 2: Score Dashlets ── */}
                        <div>
                          <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
                            Match Scorecard
                          </p>
                          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">

                            {/* Overall Match */}
                            <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-3.5 space-y-2">
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-indigo-500">Overall Match</p>
                              <p className="text-2xl font-extrabold text-indigo-700 leading-none">{matchPct.toFixed(1)}<span className="text-sm font-semibold">%</span></p>
                              <ScoreBar value={matchPct} />
                            </div>

                            {/* Skill Score */}
                            <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-3.5 space-y-2">
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-600">Skill Match</p>
                              <p className="text-2xl font-extrabold text-emerald-700 leading-none">{skillPct.toFixed(1)}<span className="text-sm font-semibold">%</span></p>
                              <ScoreBar value={skillPct} />
                            </div>

                            {/* Experience Score */}
                            <div className="rounded-xl border border-violet-100 bg-violet-50/60 p-3.5 space-y-2">
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-violet-600">Exp. Match</p>
                              <p className="text-2xl font-extrabold text-violet-700 leading-none">{expPct.toFixed(1)}<span className="text-sm font-semibold">%</span></p>
                              <ScoreBar value={expPct} />
                            </div>

                            {/* Availability */}
                            <div className={cn(
                              "rounded-xl border p-3.5 space-y-2",
                              m.availability_match
                                ? "border-emerald-100 bg-emerald-50/60"
                                : "border-amber-100 bg-amber-50/60"
                            )}>
                              <p className={cn(
                                "text-[10px] font-semibold uppercase tracking-wide",
                                m.availability_match ? "text-emerald-600" : "text-amber-600"
                              )}>Availability</p>
                              <div className="flex items-center gap-1.5">
                                <span className={cn(
                                  "h-2.5 w-2.5 rounded-full shrink-0",
                                  m.availability_match ? "bg-emerald-500" : "bg-amber-400"
                                )} />
                                <p className={cn(
                                  "text-base font-extrabold leading-none",
                                  m.availability_match ? "text-emerald-700" : "text-amber-700"
                                )}>
                                  {m.availability_match ? "Available" : "Limited"}
                                </p>
                              </div>
                              {availPct > 0 && (
                                <p className="text-xs text-slate-500 font-medium">{availPct.toFixed(0)}% capacity free</p>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* ── Section 3: Skills Analysis ── */}
                        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
                          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Skills Analysis</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {m.skills_matched && m.skills_matched.length > 0 ? (
                              <div>
                                <p className="mb-2 text-xs font-semibold text-emerald-700 flex items-center gap-1">
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                  Matched Skills
                                  <span className="ml-1 rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold">{m.skills_matched.length}</span>
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {m.skills_matched.map((s) => (
                                    <span key={s} className="rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                                      {s}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
                                No matched skills data
                              </div>
                            )}

                            {m.skill_gaps && m.skill_gaps.length > 0 ? (
                              <div>
                                <p className="mb-2 text-xs font-semibold text-red-600 flex items-center gap-1">
                                  <X className="h-3.5 w-3.5" />
                                  Skill Gaps
                                  <span className="ml-1 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold">{m.skill_gaps.length}</span>
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {m.skill_gaps.map((s) => (
                                    <span key={s} className="rounded-full bg-red-50 border border-red-200 px-2.5 py-0.5 text-xs font-medium text-red-600">
                                      {s}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
                                <CheckCircle2 className="h-4 w-4 shrink-0" /> All mandatory skills matched
                              </div>
                            )}
                          </div>
                        </div>

                        {/* ── Section 4: AI Evaluation Summary ── */}
                        {m.explanation.length > 0 && (
                          <details className="group">
                            <summary className="cursor-pointer list-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 flex items-center justify-between transition-colors hover:bg-slate-100">
                              <span className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                                <span className="text-base">🤖</span>
                                AI Evaluation Summary
                              </span>
                              <span className="text-[10px] text-slate-400 group-open:hidden">Click to expand ▼</span>
                              <span className="text-[10px] text-slate-400 hidden group-open:inline">Click to collapse ▲</span>
                            </summary>
                            <div className="mt-2 rounded-xl border border-indigo-100 bg-indigo-50/40 px-5 py-4">
                              <ul className="space-y-2">
                                {m.explanation.map((line, i) => (
                                  <li key={i} className="text-xs text-slate-700 flex gap-2.5 items-start">
                                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                                    <span>{line}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </details>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            ) : matches?.status === "NO_MATCH" ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-500 gap-3">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-50">
                  <AlertCircle className="h-8 w-8 text-amber-400" />
                </div>
                <p className="text-base font-semibold text-slate-700">No Matching Candidates Found</p>
                <p className="text-sm text-center max-w-md text-slate-500">
                  {matches.message ??
                    "None of the team members had sufficient skill or semantic similarity to this job description."}
                </p>
                <p className="text-xs text-slate-400">
                  Consider expanding required skills or checking if team member profiles are up to date.
                </p>
              </div>
            ) : (
              correlationId && (
                <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                  <Spinner className="h-8 w-8 mb-3" />
                  <p className="text-sm">AI pipeline is running…</p>
                  <p className="text-xs mt-1">This usually takes 15–30 seconds</p>
                </div>
              )
            )}
          </div>
        )}
      </div>
    </>
  );
}
